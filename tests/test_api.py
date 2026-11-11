"""JSON endpoints used by static/js/order_form.js."""

from tests.conftest import login
from tests.test_order_status import cleanup, create_draft, stock_of, status_of  # noqa: F401


# ---- /api/products/<id> ----

def test_product_lookup_requires_login(client):
    response = client.get("/api/products/1")
    assert response.status_code == 401
    assert response.get_json() == {"ok": False, "message": "Authentication required"}


def test_product_lookup_returns_price_and_stock(sales_client):
    response = sales_client.get("/api/products/1")
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["product_code"] == "SP-540"
    assert data["price"] == "12500.00"       # string, exact 2 dp
    assert isinstance(data["stock_quantity"], int)


def test_product_lookup_unknown_is_404_json(sales_client):
    response = sales_client.get("/api/products/999999")
    assert response.status_code == 404
    assert response.get_json() == {"ok": False, "message": "Product not found."}


def test_inactive_product_hidden_from_sales_but_visible_to_admin(sales_client, app):
    assert sales_client.get("/api/products/8").status_code == 404   # STR-GI is inactive

    admin_client = app.test_client()
    login(admin_client, "admin@example.com", "Admin@123")
    response = admin_client.get("/api/products/8")
    assert response.status_code == 200
    assert response.get_json()["is_active"] is False


# ---- /api/orders/<id>/confirm and /cancel ----

def test_confirm_and_cancel_via_api(sales_client, app, cleanup):
    before = stock_of(app, 1)
    order_id = create_draft(sales_client, [(1, 2)])

    response = sales_client.post("/api/orders/%d/confirm" % order_id)
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["status"] == "Confirmed"
    assert "Stock has been deducted" in data["message"]
    assert stock_of(app, 1) == before - 2

    # Second confirm: 409 with the business message, nothing changes.
    response = sales_client.post("/api/orders/%d/confirm" % order_id)
    assert response.status_code == 409
    assert response.get_json()["ok"] is False
    assert "already Confirmed" in response.get_json()["message"]
    assert stock_of(app, 1) == before - 2

    response = sales_client.post("/api/orders/%d/cancel" % order_id)
    assert response.status_code == 200
    assert response.get_json()["status"] == "Cancelled"
    assert stock_of(app, 1) == before

    response = sales_client.post("/api/orders/%d/cancel" % order_id)
    assert response.status_code == 409
    assert "already cancelled" in response.get_json()["message"]


def test_confirm_shortfall_via_api_is_409(sales_client, app, cleanup):
    inverters_before = stock_of(app, 4)
    order_id = create_draft(sales_client, [(4, inverters_before + 1)])
    response = sales_client.post("/api/orders/%d/confirm" % order_id)
    assert response.status_code == 409
    expected = "INV-10K: need %d, only %d in stock" % (inverters_before + 1, inverters_before)
    assert expected in response.get_json()["message"]
    assert status_of(app, order_id) == "Draft"


def test_api_actions_on_others_order_are_403(admin_client, app, cleanup):
    order_id = create_draft(admin_client, [(1, 1)])
    sales_client = app.test_client()
    login(sales_client, "sales@example.com", "Sales@123")

    for action in ("confirm", "cancel"):
        response = sales_client.post("/api/orders/%d/%s" % (order_id, action))
        assert response.status_code == 403
        assert response.get_json() == {"ok": False, "message": "You do not have access to this order."}
    assert status_of(app, order_id) == "Draft"


def test_api_actions_require_login(client):
    response = client.post("/api/orders/1/confirm")
    assert response.status_code == 401
    assert response.get_json() == {"ok": False, "message": "Authentication required"}


# ---- GET /api/products (list, search, paging) ----

def test_product_list_is_active_only_and_paged(sales_client):
    response = sales_client.get("/api/products?per_page=3")
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["page"] == 1 and data["per_page"] == 3
    assert data["total"] >= 7                       # 7 active seeded products
    assert data["pages"] == (data["total"] + 2) // 3
    assert len(data["items"]) == 3
    codes = [p["product_code"] for p in data["items"]]
    assert "STR-GI" not in codes                    # inactive never listed

    page2 = sales_client.get("/api/products?per_page=3&page=2").get_json()
    assert page2["page"] == 2
    assert not set(codes) & set(p["product_code"] for p in page2["items"])


def test_product_list_search_and_category(sales_client):
    data = sales_client.get("/api/products?q=inverter").get_json()
    assert sorted(p["product_code"] for p in data["items"]) == ["INV-10K", "INV-5K"]
    assert data["total"] == 2

    data = sales_client.get("/api/products?category=Batteries").get_json()
    assert [p["product_code"] for p in data["items"]] == ["BAT-150"]
    assert data["items"][0]["price"] == "65000.00"


def test_product_list_ignores_bad_paging_values(sales_client):
    data = sales_client.get("/api/products?page=abc&per_page=-5").get_json()
    assert data["page"] == 1 and data["per_page"] == 20

    data = sales_client.get("/api/products?per_page=1000").get_json()
    assert data["per_page"] == 100                  # capped


def test_product_list_requires_login(client):
    assert client.get("/api/products").status_code == 401


# ---- POST /api/orders and GET /api/orders/<id> ----

NEW_ORDER = {
    "customer_id": 1,
    "order_date": "2026-03-15",
    "discount_percentage": "10",
    "items": [{"product_id": 1, "quantity": 2}, {"product_id": 7, "quantity": 3}],
}


def test_create_order_via_api_returns_201_with_server_totals(sales_client, app, cleanup):
    payload = dict(NEW_ORDER)
    payload["grand_total"] = "1.00"                 # must be ignored
    payload["items"] = [dict(i, rate="1.00") for i in NEW_ORDER["items"]]

    response = sales_client.post("/api/orders", json=payload)
    assert response.status_code == 201
    data = response.get_json()
    assert data["ok"] is True
    assert data["status"] == "Draft"
    assert data["order_number"].startswith("SO-2026-")
    assert data["customer"] == {"id": 1, "name": "Sunrise Traders"}
    assert data["created_by"]["name"] == "Sales User"
    assert data["subtotal"] == "25450.00"
    assert data["discount_amount"] == "2545.00"
    assert data["grand_total"] == "22905.00"
    assert data["items"][0] == {
        "product_id": 1, "product_code": "SP-540", "product_name": "Solar Panel 540W Mono PERC",
        "quantity": 2, "rate": "12500.00", "amount": "25000.00",
    }

    again = sales_client.get("/api/orders/%d" % data["id"]).get_json()
    assert again["grand_total"] == "22905.00"
    assert len(again["items"]) == 2


def test_create_order_via_api_uses_same_validation_as_web(sales_client, cleanup):
    response = sales_client.post("/api/orders", json={
        "customer_id": 5,                            # inactive
        "discount_percentage": "25",
        "items": [{"product_id": 1, "quantity": 0}, {"product_id": 1, "quantity": 1}],
    })
    assert response.status_code == 400
    data = response.get_json()
    assert data["ok"] is False
    assert data["message"] == "Validation failed."
    assert "The selected customer is not available." in data["errors"]
    assert "Discount must be between 0 and 20 percent." in data["errors"]
    assert any("quantity must be a whole number greater than zero" in e for e in data["errors"])
    assert any("already on the order" in e for e in data["errors"])


def test_create_order_via_api_rejects_bad_bodies(sales_client):
    assert sales_client.post("/api/orders", data="not json",
                             content_type="application/json").status_code == 400
    assert sales_client.post("/api/orders", json=[1, 2]).status_code == 400
    assert sales_client.post("/api/orders", json={"customer_id": 1, "items": "x"}).status_code == 400
    response = sales_client.post("/api/orders", json={"customer_id": 1, "items": []})
    assert response.status_code == 400
    assert "Add at least one item to the order." in response.get_json()["errors"]


def test_create_order_via_api_requires_login(client):
    assert client.post("/api/orders", json=NEW_ORDER).status_code == 401


def test_get_order_enforces_ownership(admin_client, app, cleanup):
    admin_order = admin_client.post("/api/orders", json=NEW_ORDER).get_json()
    sales_client = app.test_client()
    login(sales_client, "sales@example.com", "Sales@123")

    response = sales_client.get("/api/orders/%d" % admin_order["id"])
    assert response.status_code == 403
    assert response.get_json() == {"ok": False, "message": "You do not have access to this order."}
    assert sales_client.get("/api/orders/999999").status_code == 404

    assert admin_client.get("/api/orders/%d" % admin_order["id"]).status_code == 200


def test_full_api_lifecycle(sales_client, app, cleanup):
    before = stock_of(app, 1)
    created = sales_client.post("/api/orders", json={
        "customer_id": 1, "items": [{"product_id": 1, "quantity": 2}]}).get_json()
    order_id = created["id"]

    assert sales_client.post("/api/orders/%d/confirm" % order_id).status_code == 200
    assert sales_client.get("/api/orders/%d" % order_id).get_json()["status"] == "Confirmed"
    assert stock_of(app, 1) == before - 2

    assert sales_client.post("/api/orders/%d/confirm" % order_id).status_code == 409
    assert sales_client.post("/api/orders/%d/cancel" % order_id).status_code == 200
    assert stock_of(app, 1) == before
    assert sales_client.post("/api/orders/%d/cancel" % order_id).status_code == 409


def test_admin_only_endpoint_is_403_for_sales(sales_client):
    response = sales_client.get("/api/admin/ping")
    assert response.status_code == 403
    assert response.get_json() == {"ok": False, "message": "Admin access required"}
