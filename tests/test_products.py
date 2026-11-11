"""Product list, filters, validation, delete rules and stock adjustment."""

from decimal import Decimal

import pytest

from app.db import get_db
from app.services.product_service import parse_money
from tests.conftest import login


@pytest.fixture
def cleanup(app):
    """Remove anything the tests created, even if a test fails midway."""
    yield
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "DELETE FROM stock_movements WHERE product_id IN "
            "(SELECT id FROM products WHERE product_code LIKE 'TEST-%')"
        )
        cursor.execute("DELETE FROM products WHERE product_code LIKE 'TEST-%'")
        db.commit()
        cursor.close()


def fetch_product(app, product_code):
    with app.app_context():
        cursor = get_db().cursor(dictionary=True)
        cursor.execute(
            "SELECT id, price, stock_quantity, is_active FROM products WHERE product_code = %s",
            (product_code,),
        )
        row = cursor.fetchone()
        cursor.close()
        return row


def fetch_movements(app, product_id):
    with app.app_context():
        cursor = get_db().cursor(dictionary=True)
        cursor.execute(
            "SELECT movement_type, quantity_change, reason FROM stock_movements "
            "WHERE product_id = %s ORDER BY id",
            (product_id,),
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows


def create_test_product(client, code="TEST-001", stock="10", **extra):
    data = {"product_code": code, "name": "Test Widget " + code, "category": "Test Cat",
            "price": "99.50", "stock_quantity": stock}
    data.update(extra)
    return client.post("/products/new", data=data, follow_redirects=True)


# ---- Money parsing ----

def test_parse_money_rounds_half_up():
    assert parse_money("2.345") == Decimal("2.35")
    assert parse_money("2.344") == Decimal("2.34")
    assert parse_money(" 10 ") == Decimal("10.00")
    assert parse_money("abc") is None
    assert parse_money("") is None


# ---- Listing and filters ----

def test_list_shows_active_products_only_by_default(admin_client):
    response = admin_client.get("/products/")
    assert response.status_code == 200
    assert b"SP-540" in response.data
    assert b"STR-GI" not in response.data  # seeded inactive product


def test_search_by_code_and_name(admin_client):
    assert b"String Inverter 5kW" in admin_client.get("/products/?q=inv-5k").data
    assert b"MC4-PAIR" in admin_client.get("/products/?q=connector").data
    assert b"No products found" in admin_client.get("/products/?q=zzzz").data


def test_filter_by_category(admin_client):
    response = admin_client.get("/products/?category=Inverters")
    assert b"INV-5K" in response.data
    assert b"SP-540" not in response.data


def test_admin_filters_inactive(admin_client):
    response = admin_client.get("/products/?status=inactive")
    assert b"STR-GI" in response.data
    assert b"SP-540" not in response.data


def test_sales_sees_active_only_and_no_admin_controls(sales_client):
    response = sales_client.get("/products/?status=all")
    assert b"STR-GI" not in response.data
    assert b"New product" not in response.data
    assert b"Adjust stock" not in response.data
    assert b"History" in response.data  # read-only link is fine


# ---- Create and validation ----

def test_sales_cannot_create(sales_client):
    assert sales_client.get("/products/new").status_code == 403


def test_admin_creates_product_with_opening_movement(admin_client, app, cleanup):
    response = create_test_product(admin_client, "test-001", stock="10")
    assert b"was created" in response.data

    product = fetch_product(app, "TEST-001")  # code is upper-cased by the server
    assert product is not None
    assert product["price"] == Decimal("99.50")
    assert product["stock_quantity"] == 10

    movements = fetch_movements(app, product["id"])
    assert len(movements) == 1
    assert movements[0]["movement_type"] == "opening"
    assert movements[0]["quantity_change"] == 10


def test_create_with_zero_stock_writes_no_movement(admin_client, app, cleanup):
    create_test_product(admin_client, "TEST-002", stock="0")
    product = fetch_product(app, "TEST-002")
    assert fetch_movements(app, product["id"]) == []


def test_duplicate_product_code_rejected(admin_client, cleanup):
    response = admin_client.post("/products/new", data={
        "product_code": "sp-540", "name": "Duplicate", "price": "1", "stock_quantity": "0"})
    assert response.status_code == 400
    assert b"already used by another product" in response.data


def test_negative_price_and_stock_rejected(admin_client, cleanup):
    response = admin_client.post("/products/new", data={
        "product_code": "TEST-NEG", "name": "Neg", "price": "-5", "stock_quantity": "-1"})
    assert response.status_code == 400
    assert b"Price cannot be negative." in response.data
    assert b"Opening stock cannot be negative." in response.data


def test_non_numeric_price_rejected(admin_client, cleanup):
    response = admin_client.post("/products/new", data={
        "product_code": "TEST-NAN", "name": "NaN", "price": "ten", "stock_quantity": "1"})
    assert response.status_code == 400
    assert b"Price must be a number." in response.data


def test_required_fields(admin_client, cleanup):
    response = admin_client.post("/products/new", data={"product_code": "", "name": "", "price": ""})
    assert response.status_code == 400
    assert b"Product code is required." in response.data
    assert b"Name is required." in response.data


# ---- Edit ----

def test_edit_keeps_own_code_and_does_not_touch_stock(admin_client, app, cleanup):
    create_test_product(admin_client, "TEST-EDIT", stock="7")
    product = fetch_product(app, "TEST-EDIT")

    response = admin_client.post(
        "/products/%d/edit" % product["id"],
        data={"product_code": "TEST-EDIT", "name": "Test Renamed", "price": "120.005",
              "stock_quantity": "999"},  # must be ignored
        follow_redirects=True,
    )
    assert b"was updated" in response.data

    after = fetch_product(app, "TEST-EDIT")
    assert after["price"] == Decimal("120.01")  # rounded half up
    assert after["stock_quantity"] == 7


def test_edit_to_existing_code_rejected(admin_client, app, cleanup):
    create_test_product(admin_client, "TEST-A")
    product = fetch_product(app, "TEST-A")
    response = admin_client.post(
        "/products/%d/edit" % product["id"],
        data={"product_code": "SP-540", "name": "X", "price": "1"},
    )
    assert response.status_code == 400
    assert b"already used by another product" in response.data


# ---- Delete ----

def test_delete_blocked_when_stock_movements_exist(admin_client, app, cleanup):
    create_test_product(admin_client, "TEST-DEL1", stock="5")  # has an opening movement
    product = fetch_product(app, "TEST-DEL1")
    response = admin_client.post("/products/%d/delete" % product["id"], follow_redirects=True)
    assert b"cannot be deleted because it is referenced by 0 order line(s) and 1 stock movement(s)" in response.data
    assert fetch_product(app, "TEST-DEL1") is not None


def test_delete_allowed_when_nothing_references_it(admin_client, app, cleanup):
    create_test_product(admin_client, "TEST-DEL2", stock="0")  # no movement
    product = fetch_product(app, "TEST-DEL2")
    response = admin_client.post("/products/%d/delete" % product["id"], follow_redirects=True)
    assert b"was deleted" in response.data
    assert fetch_product(app, "TEST-DEL2") is None


def test_seeded_product_delete_is_blocked(admin_client):
    response = admin_client.post("/products/1/delete", follow_redirects=True)
    assert b"cannot be deleted" in response.data


# ---- Adjust stock ----

def test_sales_cannot_adjust_stock(sales_client):
    assert sales_client.get("/products/1/adjust-stock").status_code == 403
    assert sales_client.post("/products/1/adjust-stock", data={}).status_code == 403


def test_adjust_stock_in_and_out(admin_client, app, cleanup):
    create_test_product(admin_client, "TEST-ADJ", stock="10")
    product = fetch_product(app, "TEST-ADJ")
    url = "/products/%d/adjust-stock" % product["id"]

    response = admin_client.post(url, data={"direction": "in", "quantity": "5",
                                            "reason": "Found extra in warehouse"},
                                 follow_redirects=True)
    assert b"changed by +5. New quantity: 15." in response.data

    response = admin_client.post(url, data={"direction": "out", "quantity": "3",
                                            "reason": "Damaged"},
                                 follow_redirects=True)
    assert b"changed by -3. New quantity: 12." in response.data

    assert fetch_product(app, "TEST-ADJ")["stock_quantity"] == 12
    movements = fetch_movements(app, product["id"])
    assert [m["quantity_change"] for m in movements] == [10, 5, -3]
    assert movements[1]["movement_type"] == "adjustment"
    assert movements[2]["reason"] == "Damaged"


def test_adjust_stock_requires_reason(admin_client, app, cleanup):
    create_test_product(admin_client, "TEST-RSN", stock="10")
    product = fetch_product(app, "TEST-RSN")
    response = admin_client.post("/products/%d/adjust-stock" % product["id"],
                                 data={"direction": "in", "quantity": "1", "reason": "   "})
    assert response.status_code == 400
    assert b"Reason is required." in response.data
    assert fetch_product(app, "TEST-RSN")["stock_quantity"] == 10


def test_adjust_stock_rejects_zero_and_non_numeric_quantity(admin_client, app, cleanup):
    create_test_product(admin_client, "TEST-QTY", stock="10")
    product = fetch_product(app, "TEST-QTY")
    url = "/products/%d/adjust-stock" % product["id"]

    response = admin_client.post(url, data={"direction": "in", "quantity": "0", "reason": "x"})
    assert b"Quantity must be greater than zero." in response.data

    response = admin_client.post(url, data={"direction": "in", "quantity": "five", "reason": "x"})
    assert b"Quantity must be a whole number." in response.data


def test_adjust_stock_rejects_going_negative(admin_client, app, cleanup):
    create_test_product(admin_client, "TEST-NEGSTK", stock="4")
    product = fetch_product(app, "TEST-NEGSTK")
    response = admin_client.post("/products/%d/adjust-stock" % product["id"],
                                 data={"direction": "out", "quantity": "5", "reason": "Oops"})
    assert response.status_code == 400
    assert b"Cannot remove 5 units: only 4 in stock" in response.data

    # Nothing changed and no movement was written.
    assert fetch_product(app, "TEST-NEGSTK")["stock_quantity"] == 4
    assert len(fetch_movements(app, product["id"])) == 1


def test_movement_history_page(admin_client, app, cleanup):
    create_test_product(admin_client, "TEST-HIST", stock="2")
    product = fetch_product(app, "TEST-HIST")
    url = "/products/%d/movements" % product["id"]

    response = admin_client.get(url)
    assert response.status_code == 200
    assert b"opening" in response.data
    assert b"Opening stock" in response.data

    # Separate client: admin_client and sales_client share one, so both cannot be used together.
    sales_client = app.test_client()
    login(sales_client, "sales@example.com", "Sales@123")

    # Sales may view history of an active product...
    assert sales_client.get(url).status_code == 200
    # ...but not of an inactive one.
    admin_client.post("/products/%d/deactivate" % product["id"])
    assert sales_client.get(url).status_code == 404
