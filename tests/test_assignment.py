"""The nine required assignment cases (see TESTING.md)."""
# Seed data used: products 1 SP-540 (12500.00), 4 INV-10K (lowest stock), 7 MC4-PAIR (150.00); customer 1.

import io
from decimal import Decimal

import pytest

from app.db import get_db
from tests.conftest import login


# ---- helpers ----

@pytest.fixture
def cleanup(app):
    """Snapshot stock and the last order id; put everything back afterwards."""
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
        cursor.execute(
            "DELETE FROM stock_movements WHERE product_id IN "
            "(SELECT id FROM products WHERE product_code LIKE 'CSV-%')")
        cursor.execute("DELETE FROM products WHERE product_code LIKE 'CSV-%'")
        db.commit()
        cursor.close()


def stock_of(app, product_id):
    with app.app_context():
        cursor = get_db().cursor()
        cursor.execute("SELECT stock_quantity FROM products WHERE id = %s", (product_id,))
        return cursor.fetchone()[0]


def order_row(app, order_id):
    with app.app_context():
        cursor = get_db().cursor(dictionary=True)
        cursor.execute("SELECT * FROM sales_orders WHERE id = %s", (order_id,))
        return cursor.fetchone()


def movement_count(app, order_id):
    with app.app_context():
        cursor = get_db().cursor()
        cursor.execute("SELECT COUNT(*) FROM stock_movements WHERE sales_order_id = %s", (order_id,))
        return cursor.fetchone()[0]


def post_order(client, items, discount="0"):
    """items: list of (product_id, quantity). Returns the raw response."""
    return client.post("/orders/new", data={
        "customer_id": "1",
        "order_date": "2026-05-01",
        "discount_percentage": discount,
        "product_id": [str(p) for p, _ in items],
        "quantity": [str(q) for _, q in items],
    })


def create_draft(client, items, discount="0"):
    response = post_order(client, items, discount)
    assert response.status_code == 302, response.data
    return int(response.headers["Location"].rstrip("/").split("/")[-1])


def confirm(client, order_id):
    return client.post("/orders/%d/confirm" % order_id, follow_redirects=True)


def cancel(client, order_id):
    return client.post("/orders/%d/cancel" % order_id, follow_redirects=True)


# ---- 1. Multi-item order with discount -> correct subtotal / grand total ----

def test_multi_item_order_with_discount_totals(sales_client, app, cleanup):
    # 2 x 12500.00 + 3 x 150.00 = 25450.00; 10% = 2545.00; total 22905.00
    order_id = create_draft(sales_client, [(1, 2), (7, 3)], discount="10")
    order = order_row(app, order_id)

    assert order["subtotal"] == Decimal("25450.00")
    assert order["discount_amount"] == Decimal("2545.00")
    assert order["grand_total"] == Decimal("22905.00")
    assert order["status"] == "Draft"


# ---- 2. Zero / negative quantity rejected ----

def test_zero_and_negative_quantity_rejected(sales_client, app, cleanup):
    before = order_row(app, 10**9)  # sanity: helper works on missing ids
    assert before is None

    for bad_qty in (0, -1):
        response = post_order(sales_client, [(1, bad_qty)])
        assert response.status_code == 400
        assert b"quantity must be a whole number greater than zero" in response.data


# ---- 3. Discount < 0 or > 20 rejected ----

def test_discount_outside_0_to_20_rejected(sales_client, cleanup):
    for bad_discount in ("-1", "20.01", "50"):
        response = post_order(sales_client, [(1, 1)], discount=bad_discount)
        assert response.status_code == 400, bad_discount
        assert b"Discount must be between 0 and 20 percent." in response.data

    # Boundaries are allowed.
    assert post_order(sales_client, [(1, 1)], discount="0").status_code == 302
    assert post_order(sales_client, [(1, 1)], discount="20").status_code == 302


# ---- 4. Confirm with sufficient stock -> status Confirmed + stock deducted ----

def test_confirm_with_sufficient_stock(sales_client, app, cleanup):
    panels_before = stock_of(app, 1)
    connectors_before = stock_of(app, 7)
    order_id = create_draft(sales_client, [(1, 2), (7, 3)])

    response = confirm(sales_client, order_id)
    assert b"confirmed. Stock has been deducted." in response.data

    assert order_row(app, order_id)["status"] == "Confirmed"
    assert stock_of(app, 1) == panels_before - 2
    assert stock_of(app, 7) == connectors_before - 3
    assert movement_count(app, order_id) == 2        # one order_confirm per item


# ---- 5. Confirm with ONE insufficient item -> no changes at all ----

def test_confirm_with_one_insufficient_item_changes_nothing(sales_client, app, cleanup):
    panels_before = stock_of(app, 1)
    inverters_before = stock_of(app, 4)
    # Panels are fine; inverters are one short.
    order_id = create_draft(sales_client, [(1, 1), (4, inverters_before + 1)])

    response = confirm(sales_client, order_id)
    assert b"Cannot confirm" in response.data
    assert ("INV-10K: need %d, only %d in stock" % (inverters_before + 1, inverters_before)).encode() in response.data

    assert order_row(app, order_id)["status"] == "Draft"
    assert stock_of(app, 1) == panels_before          # the OK item was not deducted either
    assert stock_of(app, 4) == inverters_before
    assert movement_count(app, order_id) == 0


# ---- 6. Repeated confirm -> no extra deduction ----

def test_repeated_confirm_does_not_deduct_again(sales_client, app, cleanup):
    before = stock_of(app, 1)
    order_id = create_draft(sales_client, [(1, 2)])

    confirm(sales_client, order_id)
    assert stock_of(app, 1) == before - 2

    response = confirm(sales_client, order_id)
    assert b"is already Confirmed and cannot be confirmed." in response.data
    assert stock_of(app, 1) == before - 2
    assert movement_count(app, order_id) == 1


# ---- 7. Cancel a Confirmed order -> stock restored exactly once ----

def test_cancel_confirmed_restores_stock_once(sales_client, app, cleanup):
    before = stock_of(app, 1)
    order_id = create_draft(sales_client, [(1, 2)])
    confirm(sales_client, order_id)
    assert stock_of(app, 1) == before - 2

    response = cancel(sales_client, order_id)
    assert b"cancelled. Stock has been restored." in response.data
    assert order_row(app, order_id)["status"] == "Cancelled"
    assert stock_of(app, 1) == before
    assert movement_count(app, order_id) == 2        # order_confirm + order_cancel

    # Cancelling again must NOT add stock a second time.
    response = cancel(sales_client, order_id)
    assert b"is already cancelled." in response.data
    assert stock_of(app, 1) == before
    assert movement_count(app, order_id) == 2


# ---- 8. Sales user accessing another user's order -> 403 ----

def test_sales_user_gets_403_on_another_users_order(admin_client, app, cleanup):
    admin_order_id = create_draft(admin_client, [(1, 1)])

    sales_client = app.test_client()
    login(sales_client, "sales@example.com", "Sales@123")

    assert sales_client.get("/orders/%d" % admin_order_id).status_code == 403
    assert sales_client.get("/orders/%d/edit" % admin_order_id).status_code == 403
    assert sales_client.post("/orders/%d/confirm" % admin_order_id).status_code == 403
    assert sales_client.post("/orders/%d/cancel" % admin_order_id).status_code == 403

    api = sales_client.get("/api/orders/%d" % admin_order_id)
    assert api.status_code == 403
    assert api.get_json()["ok"] is False

    assert order_row(app, admin_order_id)["status"] == "Draft"


# ---- 9. CSV with one invalid row -> zero products imported ----

def test_csv_with_one_invalid_row_imports_nothing(admin_client, app, cleanup):
    csv_text = (
        "product_code,product_name,category,price,stock_quantity,status\n"
        "CSV-001,Good product one,Test,100.00,5,Active\n"
        "CSV-002,Good product two,Test,200.00,3,Active\n"
        "CSV-003,Bad price here,Test,abc,1,Active\n"
    )
    response = admin_client.post(
        "/products/import",
        data={"file": (io.BytesIO(csv_text.encode("utf-8")), "mixed.csv")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert b"price &#39;abc&#39; is not a number." in response.data
    assert b"No products were saved." in response.data

    with app.app_context():
        cursor = get_db().cursor()
        cursor.execute("SELECT COUNT(*) FROM products WHERE product_code LIKE 'CSV-%'")
        assert cursor.fetchone()[0] == 0
