"""Sales order creation, calculation, validation, editing and ownership."""

from decimal import Decimal

import pytest

from app.db import get_db
from app.services.order_service import calculate_totals, next_order_number
from tests.conftest import login


@pytest.fixture
def cleanup(app):
    """Delete any orders created during a test (ids above the starting max)."""
    with app.app_context():
        cursor = get_db().cursor()
        cursor.execute("SELECT COALESCE(MAX(id), 0) FROM sales_orders")
        start_max = cursor.fetchone()[0]
        cursor.close()

    yield

    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM sales_order_items WHERE sales_order_id > %s", (start_max,))
        cursor.execute("DELETE FROM sales_orders WHERE id > %s", (start_max,))
        db.commit()
        cursor.close()


def fetch_order(app, order_id):
    with app.app_context():
        cursor = get_db().cursor(dictionary=True)
        cursor.execute("SELECT * FROM sales_orders WHERE id = %s", (order_id,))
        order = cursor.fetchone()
        cursor.execute(
            "SELECT product_id, quantity, rate, amount FROM sales_order_items "
            "WHERE sales_order_id = %s ORDER BY id", (order_id,))
        items = cursor.fetchall()
        cursor.close()
        return order, items


def order_id_from(response):
    """After a successful save we are redirected to /orders/<id>."""
    assert response.status_code == 302, response.data
    return int(response.headers["Location"].rstrip("/").split("/")[-1])


# Seed: SP-540 (1) 12500.00, MC4-PAIR (7) 150.00; customer 5 and product 8 (STR-GI) are inactive.
BASIC_ORDER = {
    "customer_id": "1",
    "order_date": "2026-03-15",
    "discount_percentage": "10",
    "product_id": ["1", "7"],
    "quantity": ["2", "3"],
}


# ---- Pure calculation ----

def test_calculate_totals_basic():
    items = [
        {"quantity": 2, "rate": Decimal("12500.00")},
        {"quantity": 3, "rate": Decimal("150.00")},
    ]
    totals = calculate_totals(items, Decimal("10.00"))
    assert items[0]["amount"] == Decimal("25000.00")
    assert items[1]["amount"] == Decimal("450.00")
    assert totals == {
        "subtotal": Decimal("25450.00"),
        "discount_amount": Decimal("2545.00"),
        "grand_total": Decimal("22905.00"),
    }


def test_calculate_totals_rounds_half_up():
    # 3 x 99.99 = 299.97; 7.5% of that = 22.49775 -> 22.50; total 277.47
    items = [{"quantity": 3, "rate": Decimal("99.99")}]
    totals = calculate_totals(items, Decimal("7.50"))
    assert totals["discount_amount"] == Decimal("22.50")
    assert totals["grand_total"] == Decimal("277.47")


def test_calculate_totals_zero_discount():
    items = [{"quantity": 1, "rate": Decimal("0.10")}, {"quantity": 1, "rate": Decimal("0.20")}]
    totals = calculate_totals(items, Decimal("0"))
    assert totals["subtotal"] == Decimal("0.30")  # no float drift
    assert totals["grand_total"] == Decimal("0.30")


# ---- Create ----

def test_create_order_stores_server_side_rates_and_totals(sales_client, app, cleanup):
    # Browser tries to send its own rate and total: they must be ignored.
    data = dict(BASIC_ORDER)
    data["rate"] = ["1.00", "1.00"]
    data["grand_total"] = "5.00"

    order_id = order_id_from(sales_client.post("/orders/new", data=data))
    order, items = fetch_order(app, order_id)

    assert order["status"] == "Draft"
    assert order["created_by"] == 2  # seeded sales user
    assert order["discount_percentage"] == Decimal("10.00")
    assert order["subtotal"] == Decimal("25450.00")
    assert order["discount_amount"] == Decimal("2545.00")
    assert order["grand_total"] == Decimal("22905.00")

    assert [(i["product_id"], i["quantity"], i["rate"], i["amount"]) for i in items] == [
        (1, 2, Decimal("12500.00"), Decimal("25000.00")),
        (7, 3, Decimal("150.00"), Decimal("450.00")),
    ]


def test_order_numbers_follow_year_sequence(admin_client, app, cleanup):
    first = order_id_from(admin_client.post("/orders/new", data=BASIC_ORDER))
    second = order_id_from(admin_client.post("/orders/new", data=BASIC_ORDER))
    n1 = fetch_order(app, first)[0]["order_number"]
    n2 = fetch_order(app, second)[0]["order_number"]

    assert n1.startswith("SO-2026-") and len(n1) == len("SO-2026-0001")
    assert int(n2.split("-")[-1]) == int(n1.split("-")[-1]) + 1

    with app.app_context():
        assert next_order_number(1999) == "SO-1999-0001"


def test_detail_page_shows_totals(sales_client, cleanup):
    order_id = order_id_from(sales_client.post("/orders/new", data=BASIC_ORDER))
    response = sales_client.get("/orders/%d" % order_id)
    assert response.status_code == 200
    assert b"25,450.00" in response.data
    assert b"2,545.00" in response.data
    assert b"22,905.00" in response.data
    assert b"Draft" in response.data


# ---- Validation ----

def post_invalid(client, **changes):
    data = dict(BASIC_ORDER)
    data.update(changes)
    response = client.post("/orders/new", data=data)
    assert response.status_code == 400
    return response.data


def test_requires_at_least_one_item(sales_client):
    body = post_invalid(sales_client, product_id=[""], quantity=[""])
    assert b"Add at least one item to the order." in body


def test_rejects_duplicate_product(sales_client):
    body = post_invalid(sales_client, product_id=["1", "1"], quantity=["1", "2"])
    assert b"this product is already on the order" in body


def test_rejects_bad_quantities(sales_client):
    body = post_invalid(sales_client, product_id=["1", "7"], quantity=["0", "two"])
    assert body.count(b"quantity must be a whole number greater than zero") == 2


def test_rejects_discount_outside_0_to_20(sales_client):
    assert b"Discount must be between 0 and 20 percent." in post_invalid(sales_client, discount_percentage="20.01")
    assert b"Discount must be between 0 and 20 percent." in post_invalid(sales_client, discount_percentage="-1")
    assert b"Discount must be a number." in post_invalid(sales_client, discount_percentage="ten")


def test_rejects_inactive_customer_and_product(sales_client):
    body = post_invalid(sales_client, customer_id="5")
    assert b"The selected customer is not available." in body

    body = post_invalid(sales_client, product_id=["8"], quantity=["1"])
    assert b"the selected product is not available." in body


def test_rejects_unknown_customer_and_bad_date(sales_client):
    body = post_invalid(sales_client, customer_id="999999", order_date="15-03-2026")
    assert b"The selected customer is not available." in body
    assert b"Order date must be in YYYY-MM-DD format." in body


def test_blank_date_defaults_to_today(sales_client, app, cleanup):
    from datetime import date
    order_id = order_id_from(sales_client.post("/orders/new", data=dict(BASIC_ORDER, order_date="")))
    assert fetch_order(app, order_id)[0]["order_date"] == date.today()


# ---- Edit a draft ----

def test_edit_draft_changes_quantity_and_removes_row(sales_client, app, cleanup):
    order_id = order_id_from(sales_client.post("/orders/new", data=BASIC_ORDER))

    response = sales_client.get("/orders/%d/edit" % order_id)
    assert response.status_code == 200
    assert b'"product_id": "1"' in response.data
    assert b'"quantity": "3"' in response.data

    # Keep only SP-540 with qty 4, discount 5%.
    response = sales_client.post("/orders/%d/edit" % order_id, data={
        "customer_id": "2", "order_date": "2026-03-16", "discount_percentage": "5",
        "product_id": ["1"], "quantity": ["4"],
    })
    assert response.status_code == 302

    order, items = fetch_order(app, order_id)
    assert order["customer_id"] == 2
    assert str(order["order_date"]) == "2026-03-16"
    assert len(items) == 1
    assert items[0]["quantity"] == 4
    assert order["subtotal"] == Decimal("50000.00")
    assert order["discount_amount"] == Decimal("2500.00")
    assert order["grand_total"] == Decimal("47500.00")


def test_edit_with_errors_keeps_order_unchanged(sales_client, app, cleanup):
    order_id = order_id_from(sales_client.post("/orders/new", data=BASIC_ORDER))
    response = sales_client.post("/orders/%d/edit" % order_id, data={
        "customer_id": "1", "order_date": "2026-03-15", "discount_percentage": "50",
        "product_id": ["1"], "quantity": ["1"],
    })
    assert response.status_code == 400
    order, items = fetch_order(app, order_id)
    assert order["grand_total"] == Decimal("22905.00")
    assert len(items) == 2


def test_confirmed_order_cannot_be_edited(admin_client, app, cleanup):
    order_id = order_id_from(admin_client.post("/orders/new", data=BASIC_ORDER))
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE sales_orders SET status = 'Confirmed' WHERE id = %s", (order_id,))
        db.commit()

    response = admin_client.get("/orders/%d/edit" % order_id, follow_redirects=True)
    assert b"Only Draft orders can be edited." in response.data
    assert b"Edit</a>" not in response.data  # no edit button on detail page


# ---- Ownership ----

def test_sales_user_cannot_see_or_edit_other_users_order(admin_client, app, cleanup):
    admin_order_id = order_id_from(admin_client.post("/orders/new", data=BASIC_ORDER))

    sales_client = app.test_client()
    login(sales_client, "sales@example.com", "Sales@123")
    own_order_id = order_id_from(sales_client.post("/orders/new", data=BASIC_ORDER))

    # Someone else's order -> 403; an id that does not exist -> 404.
    assert sales_client.get("/orders/%d" % admin_order_id).status_code == 403
    assert sales_client.get("/orders/%d/edit" % admin_order_id).status_code == 403
    assert sales_client.post("/orders/%d/edit" % admin_order_id, data=BASIC_ORDER).status_code == 403
    assert sales_client.get("/orders/999999").status_code == 404

    assert sales_client.get("/orders/%d" % own_order_id).status_code == 200

    # The list only contains the sales user's order.
    admin_number = fetch_order(app, admin_order_id)[0]["order_number"].encode()
    own_number = fetch_order(app, own_order_id)[0]["order_number"].encode()
    listing = sales_client.get("/orders/").data
    assert own_number in listing
    assert admin_number not in listing

    # Admin sees both, with the creator column.
    listing = admin_client.get("/orders/").data
    assert own_number in listing and admin_number in listing
    assert b"Sales User" in listing


def test_order_list_filters(admin_client, app, cleanup):
    order_id = order_id_from(admin_client.post("/orders/new", data=BASIC_ORDER))
    number = fetch_order(app, order_id)[0]["order_number"].encode()

    assert number in admin_client.get("/orders/?status=Draft").data
    assert number not in admin_client.get("/orders/?status=Confirmed").data
    assert number in admin_client.get("/orders/?q=sunrise").data
    assert number not in admin_client.get("/orders/?q=zzzz").data
