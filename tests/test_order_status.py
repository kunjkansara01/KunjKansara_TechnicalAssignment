"""Confirm/cancel: stock effects, rollback on shortfall, no-op repeats, read-only, FOR UPDATE lock."""
# Stock assertions are relative to the starting stock, never hard-coded seed numbers.

import threading
import time

import mysql.connector
import pytest

from app.db import get_db
from tests.conftest import login


@pytest.fixture
def cleanup(app):
    """Snapshot product stock and the last order id; restore/delete afterwards."""
    with app.app_context():
        cursor = get_db().cursor()
        cursor.execute("SELECT COALESCE(MAX(id), 0) FROM sales_orders")
        start_max = cursor.fetchone()[0]
        cursor.execute("SELECT id, stock_quantity FROM products")
        stock_before = cursor.fetchall()
        cursor.close()

    yield

    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM stock_movements WHERE sales_order_id > %s", (start_max,))
        cursor.execute("DELETE FROM sales_order_items WHERE sales_order_id > %s", (start_max,))
        cursor.execute("DELETE FROM sales_orders WHERE id > %s", (start_max,))
        for product_id, quantity in stock_before:
            cursor.execute("UPDATE products SET stock_quantity = %s WHERE id = %s",
                           (quantity, product_id))
        db.commit()
        cursor.close()


def stock_of(app, product_id):
    with app.app_context():
        cursor = get_db().cursor()
        cursor.execute("SELECT stock_quantity FROM products WHERE id = %s", (product_id,))
        return cursor.fetchone()[0]


def status_of(app, order_id):
    with app.app_context():
        cursor = get_db().cursor()
        cursor.execute("SELECT status FROM sales_orders WHERE id = %s", (order_id,))
        return cursor.fetchone()[0]


def movements_for_order(app, order_id):
    with app.app_context():
        cursor = get_db().cursor(dictionary=True)
        cursor.execute(
            "SELECT product_id, movement_type, quantity_change, reason FROM stock_movements "
            "WHERE sales_order_id = %s ORDER BY id", (order_id,))
        return cursor.fetchall()


def create_draft(client, items):
    """items: list of (product_id, quantity). Returns the new order id."""
    data = {
        "customer_id": "1", "order_date": "2026-05-01", "discount_percentage": "0",
        "product_id": [str(p) for p, _ in items],
        "quantity": [str(q) for _, q in items],
    }
    response = client.post("/orders/new", data=data)
    assert response.status_code == 302, response.data
    return int(response.headers["Location"].rstrip("/").split("/")[-1])


# Products used: SP-540 (1), INV-10K (4, lowest stock), MC4-PAIR (7).


# ---- Confirm ----

def test_confirm_deducts_stock_and_writes_movements(sales_client, app, cleanup):
    panels_before = stock_of(app, 1)
    connectors_before = stock_of(app, 7)
    order_id = create_draft(sales_client, [(1, 2), (7, 3)])

    response = sales_client.post("/orders/%d/confirm" % order_id, follow_redirects=True)
    assert b"confirmed. Stock has been deducted." in response.data

    assert status_of(app, order_id) == "Confirmed"
    assert stock_of(app, 1) == panels_before - 2
    assert stock_of(app, 7) == connectors_before - 3

    movements = movements_for_order(app, order_id)
    assert [(m["product_id"], m["movement_type"], m["quantity_change"]) for m in movements] == [
        (1, "order_confirm", -2),
        (7, "order_confirm", -3),
    ]
    assert movements[0]["reason"].startswith("Order SO-2026-")
    assert movements[0]["reason"].endswith("confirmed")


def test_confirm_rejects_whole_order_when_any_item_is_short(sales_client, app, cleanup):
    panels_before = stock_of(app, 1)
    inverters_before = stock_of(app, 4)
    # SP-540 has plenty; ask for one more inverter than exists.
    order_id = create_draft(sales_client, [(1, 2), (4, inverters_before + 1)])

    response = sales_client.post("/orders/%d/confirm" % order_id, follow_redirects=True)
    assert b"Cannot confirm" in response.data
    expected = "INV-10K: need %d, only %d in stock" % (inverters_before + 1, inverters_before)
    assert expected.encode() in response.data

    # Nothing changed for EITHER product, status unchanged, no movements.
    assert status_of(app, order_id) == "Draft"
    assert stock_of(app, 1) == panels_before
    assert stock_of(app, 4) == inverters_before
    assert movements_for_order(app, order_id) == []


def test_confirm_lists_every_shortfall(sales_client, app, cleanup):
    panels_before = stock_of(app, 1)
    inverters_before = stock_of(app, 4)
    order_id = create_draft(sales_client, [(4, inverters_before + 1), (1, panels_before + 1)])
    response = sales_client.post("/orders/%d/confirm" % order_id, follow_redirects=True)
    assert ("SP-540: need %d, only %d in stock" % (panels_before + 1, panels_before)).encode() in response.data
    assert ("INV-10K: need %d, only %d in stock" % (inverters_before + 1, inverters_before)).encode() in response.data


def test_confirm_twice_is_a_no_op_with_error(sales_client, app, cleanup):
    before = stock_of(app, 1)
    order_id = create_draft(sales_client, [(1, 1)])
    sales_client.post("/orders/%d/confirm" % order_id)
    assert stock_of(app, 1) == before - 1

    response = sales_client.post("/orders/%d/confirm" % order_id, follow_redirects=True)
    assert b"is already Confirmed and cannot be confirmed." in response.data
    assert stock_of(app, 1) == before - 1                 # not deducted again
    assert len(movements_for_order(app, order_id)) == 1


def test_confirm_cancelled_order_is_refused(sales_client, app, cleanup):
    before = stock_of(app, 1)
    order_id = create_draft(sales_client, [(1, 1)])
    sales_client.post("/orders/%d/cancel" % order_id)
    response = sales_client.post("/orders/%d/confirm" % order_id, follow_redirects=True)
    assert b"is already Cancelled and cannot be confirmed." in response.data
    assert stock_of(app, 1) == before


def test_exact_stock_can_be_confirmed(sales_client, app, cleanup):
    inverters_before = stock_of(app, 4)
    assert inverters_before > 0, "test needs some INV-10K stock"
    order_id = create_draft(sales_client, [(4, inverters_before)])
    sales_client.post("/orders/%d/confirm" % order_id)
    assert status_of(app, order_id) == "Confirmed"
    assert stock_of(app, 4) == 0


# ---- Cancel ----

def test_cancel_draft_has_no_stock_effect(sales_client, app, cleanup):
    before = stock_of(app, 1)
    order_id = create_draft(sales_client, [(1, 5)])
    response = sales_client.post("/orders/%d/cancel" % order_id, follow_redirects=True)
    assert b"cancelled." in response.data
    assert b"Stock has been restored" not in response.data
    assert status_of(app, order_id) == "Cancelled"
    assert stock_of(app, 1) == before
    assert movements_for_order(app, order_id) == []


def test_cancel_confirmed_restores_stock_with_movements(sales_client, app, cleanup):
    panels_before = stock_of(app, 1)
    connectors_before = stock_of(app, 7)
    order_id = create_draft(sales_client, [(1, 2), (7, 3)])
    sales_client.post("/orders/%d/confirm" % order_id)
    assert stock_of(app, 1) == panels_before - 2

    response = sales_client.post("/orders/%d/cancel" % order_id, follow_redirects=True)
    assert b"cancelled. Stock has been restored." in response.data
    assert status_of(app, order_id) == "Cancelled"
    assert stock_of(app, 1) == panels_before
    assert stock_of(app, 7) == connectors_before

    movements = movements_for_order(app, order_id)
    assert [(m["product_id"], m["movement_type"], m["quantity_change"]) for m in movements] == [
        (1, "order_confirm", -2),
        (7, "order_confirm", -3),
        (1, "order_cancel", 2),
        (7, "order_cancel", 3),
    ]


def test_cancel_twice_is_a_no_op_with_error(sales_client, app, cleanup):
    before = stock_of(app, 1)
    order_id = create_draft(sales_client, [(1, 2)])
    sales_client.post("/orders/%d/confirm" % order_id)
    sales_client.post("/orders/%d/cancel" % order_id)
    assert stock_of(app, 1) == before

    response = sales_client.post("/orders/%d/cancel" % order_id, follow_redirects=True)
    assert b"is already cancelled." in response.data
    assert stock_of(app, 1) == before                     # not restored twice
    assert len(movements_for_order(app, order_id)) == 2


# ---- Read-only after status change ----

def test_confirmed_and_cancelled_orders_are_read_only(sales_client, app, cleanup):
    order_id = create_draft(sales_client, [(1, 1)])
    sales_client.post("/orders/%d/confirm" % order_id)

    detail = sales_client.get("/orders/%d" % order_id).data
    assert b">Edit</a>" not in detail
    assert b">Confirm</button>" not in detail
    assert b"Cancel order" in detail               # still cancellable

    edit = sales_client.post("/orders/%d/edit" % order_id, data={
        "customer_id": "1", "order_date": "2026-05-01", "discount_percentage": "0",
        "product_id": ["1"], "quantity": ["99"]}, follow_redirects=True)
    assert b"Only Draft orders can be edited." in edit.data

    sales_client.post("/orders/%d/cancel" % order_id)
    detail = sales_client.get("/orders/%d" % order_id).data
    assert b"Cancel order" not in detail
    assert b">Edit</a>" not in detail


def test_sales_cannot_confirm_or_cancel_others_orders(admin_client, app, cleanup):
    before = stock_of(app, 1)
    order_id = create_draft(admin_client, [(1, 1)])
    sales_client = app.test_client()
    login(sales_client, "sales@example.com", "Sales@123")

    assert sales_client.post("/orders/%d/confirm" % order_id).status_code == 403
    assert sales_client.post("/orders/%d/cancel" % order_id).status_code == 403
    assert status_of(app, order_id) == "Draft"
    assert stock_of(app, 1) == before


# ---- The lock itself: confirm must WAIT for a competing row lock, then see the committed stock ----

def test_confirm_waits_for_competing_lock_and_sees_committed_stock(sales_client, app, cleanup):
    inverters_before = stock_of(app, 4)
    assert inverters_before > 0, "test needs some INV-10K stock"
    # Our order wants every inverter in stock.
    order_id = create_draft(sales_client, [(4, inverters_before)])

    # Another connection locks the product row and sells 1 unit without committing.
    other = mysql.connector.connect(
        host=app.config["DB_HOST"], port=app.config["DB_PORT"], user=app.config["DB_USER"],
        password=app.config["DB_PASSWORD"], database=app.config["DB_NAME"],
    )
    other_cursor = other.cursor()
    other_cursor.execute("SELECT stock_quantity FROM products WHERE id = 4 FOR UPDATE")
    other_cursor.fetchall()
    other_cursor.execute("UPDATE products SET stock_quantity = %s WHERE id = 4",
                         (inverters_before - 1,))

    result = {}

    def run_confirm():
        response = sales_client.post("/orders/%d/confirm" % order_id, follow_redirects=True)
        result["body"] = response.data
        result["finished_at"] = time.time()

    thread = threading.Thread(target=run_confirm)
    started_at = time.time()
    thread.start()

    # While the other transaction holds the lock, our confirm cannot finish.
    time.sleep(1.5)
    assert thread.is_alive(), "confirm should be blocked waiting for the row lock"

    # After the other commit our confirm resumes, reads the reduced stock, and must refuse.
    other.commit()
    other_cursor.close()
    other.close()
    thread.join(timeout=10)
    assert not thread.is_alive()
    assert result["finished_at"] - started_at >= 1.5

    expected = "INV-10K: need %d, only %d in stock" % (inverters_before, inverters_before - 1)
    assert expected.encode() in result["body"]
    assert status_of(app, order_id) == "Draft"
    assert stock_of(app, 4) == inverters_before - 1
