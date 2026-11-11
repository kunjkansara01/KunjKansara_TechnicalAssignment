"""Customer list, search, create, edit, deactivate and delete rules."""

import pytest

from app.db import get_db


@pytest.fixture
def cleanup(app):
    """Remove anything the tests created, even if a test fails midway."""
    yield
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute("DELETE FROM sales_orders WHERE order_number LIKE 'TEST-%'")
        cursor.execute("DELETE FROM customers WHERE name LIKE 'Test %'")
        db.commit()
        cursor.close()


def find_customer_id(app, name):
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id FROM customers WHERE name = %s", (name,))
        row = cursor.fetchone()
        cursor.close()
        return row[0] if row else None


def insert_test_order(app, customer_id):
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO sales_orders (order_number, customer_id, order_date, status, created_by) "
            "VALUES ('TEST-1', %s, CURDATE(), 'Draft', 1)",
            (customer_id,),
        )
        db.commit()
        cursor.close()


# ---- Listing and search ----

def test_list_shows_active_customers(admin_client):
    response = admin_client.get("/customers/")
    assert response.status_code == 200
    assert b"Sunrise Traders" in response.data
    # Seeded inactive customer is hidden by default.
    assert b"Old Town Hardware" not in response.data


def test_admin_can_filter_inactive(admin_client):
    response = admin_client.get("/customers/?status=inactive")
    assert b"Old Town Hardware" in response.data
    assert b"Sunrise Traders" not in response.data


def test_sales_cannot_see_inactive_even_with_filter(sales_client):
    response = sales_client.get("/customers/?status=all")
    assert response.status_code == 200
    assert b"Old Town Hardware" not in response.data
    assert b"New customer" not in response.data
    assert b"Deactivate" not in response.data


def test_search_matches_name_email_and_mobile(admin_client):
    assert b"Patel Electricals" in admin_client.get("/customers/?q=patel").data
    assert b"Green Power Solutions" in admin_client.get("/customers/?q=greenpower").data
    assert b"Metro Infra Projects" in admin_client.get("/customers/?q=9876500004").data
    assert b"No customers found" in admin_client.get("/customers/?q=zzzzzz").data


# ---- Create ----

def test_sales_user_gets_403_on_create(sales_client):
    assert sales_client.get("/customers/new").status_code == 403
    response = sales_client.post("/customers/new", data={"name": "Test Blocked"})
    assert response.status_code == 403


def test_admin_creates_customer(admin_client, app, cleanup):
    response = admin_client.post(
        "/customers/new",
        data={"name": " Test Alpha ", "email": "ALPHA@Test.com", "mobile": "9999900001", "city": "Goa"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Customer &#39;Test Alpha&#39; was created." in response.data

    customer_id = find_customer_id(app, "Test Alpha")
    assert customer_id is not None
    # Values were trimmed and the email lower-cased by the server.
    assert b"alpha@test.com" in response.data


def test_create_requires_name(admin_client, cleanup):
    response = admin_client.post("/customers/new", data={"name": "   ", "city": "Goa"})
    assert response.status_code == 400
    assert b"Name is required." in response.data


def test_create_validates_email_and_mobile(admin_client, cleanup):
    response = admin_client.post(
        "/customers/new",
        data={"name": "Test Bad", "email": "not-an-email", "mobile": "12ab"},
    )
    assert response.status_code == 400
    assert b"Email address is not valid." in response.data
    assert b"Mobile must contain digits only." in response.data
    assert b'value="Test Bad"' in response.data


def test_optional_fields_saved_as_null(admin_client, app, cleanup):
    admin_client.post("/customers/new", data={"name": "Test Minimal"})
    customer_id = find_customer_id(app, "Test Minimal")
    with app.app_context():
        cursor = get_db().cursor()
        cursor.execute("SELECT email, mobile, city FROM customers WHERE id = %s", (customer_id,))
        assert cursor.fetchone() == (None, None, None)


# ---- Edit, deactivate, activate ----

def test_admin_edits_customer(admin_client, app, cleanup):
    admin_client.post("/customers/new", data={"name": "Test Edit Me"})
    customer_id = find_customer_id(app, "Test Edit Me")

    response = admin_client.get("/customers/%d/edit" % customer_id)
    assert b'value="Test Edit Me"' in response.data

    response = admin_client.post(
        "/customers/%d/edit" % customer_id,
        data={"name": "Test Edited", "city": "Pune"},
        follow_redirects=True,
    )
    assert b"was updated" in response.data
    assert find_customer_id(app, "Test Edited") == customer_id


def test_edit_unknown_customer_is_404(admin_client):
    assert admin_client.get("/customers/999999/edit").status_code == 404


def test_deactivate_and_activate(admin_client, app, cleanup):
    admin_client.post("/customers/new", data={"name": "Test Toggle"})
    customer_id = find_customer_id(app, "Test Toggle")

    # follow_redirects so the flash is consumed here and does not leak into the later page checks.
    response = admin_client.post("/customers/%d/deactivate" % customer_id, follow_redirects=True)
    assert b"was deactivated" in response.data
    assert b"Test Toggle" not in admin_client.get("/customers/").data
    assert b"Test Toggle" in admin_client.get("/customers/?status=inactive").data

    response = admin_client.post("/customers/%d/activate" % customer_id, follow_redirects=True)
    assert b"was activated" in response.data
    assert b"Test Toggle" in admin_client.get("/customers/").data


# ---- Delete ----

def test_delete_customer_without_orders(admin_client, app, cleanup):
    admin_client.post("/customers/new", data={"name": "Test Delete Me"})
    customer_id = find_customer_id(app, "Test Delete Me")

    response = admin_client.post("/customers/%d/delete" % customer_id, follow_redirects=True)
    assert b"Test Delete Me was deleted." in response.data
    assert find_customer_id(app, "Test Delete Me") is None


def test_delete_customer_with_orders_is_refused(admin_client, app, cleanup):
    admin_client.post("/customers/new", data={"name": "Test Has Orders"})
    customer_id = find_customer_id(app, "Test Has Orders")
    insert_test_order(app, customer_id)

    response = admin_client.post("/customers/%d/delete" % customer_id, follow_redirects=True)
    assert b"cannot be deleted because 1 order(s) reference this customer" in response.data
    assert b"Deactivate the customer instead." in response.data
    assert find_customer_id(app, "Test Has Orders") == customer_id


def test_sales_user_cannot_delete(sales_client):
    assert sales_client.post("/customers/1/delete").status_code == 403
