import io
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from decimal import Decimal
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models import Order, Product, StockMovement
from debugging import calculate_total
from conftest import login_client, order_data


def create(client, **overrides):
    result = client.post("/api/orders", json=order_data(**overrides))
    assert result.status_code == 201, result.json
    return result.json["id"]


def stock(app, product_id=1):
    with Session(app.extensions["engine"]) as db:
        return db.get(Product, product_id).stock_quantity


def test_calculation_and_untrusted_fields(client):
    data = order_data(rate=1, grand_total=1, created_by=3, status="Confirmed")
    data["items"][0]["rate"] = 1
    result = client.post("/api/orders", json=data).json
    assert (result["subtotal"], result["discount_amount"], result["grand_total"]) == (
        "4500.00",
        "450.00",
        "4050.00",
    )
    assert result["status"] == "Draft" and result["created_by"] == 1


@pytest.mark.parametrize("quantity", [0, -1, 1.5, True, "NaN", None, "9" * 5000, "0" * 5000])
def test_invalid_quantity(client, quantity):
    assert (
        client.post(
            "/api/orders",
            json=order_data(items=[{"product_id": 1, "quantity": quantity}]),
        ).status_code
        == 400
    )


@pytest.mark.parametrize("discount", [-1, 21, "NaN", "Infinity", "1.001"])
def test_invalid_discount(client, discount):
    assert (
        client.post(
            "/api/orders", json=order_data(discount_percentage=discount)
        ).status_code
        == 400
    )


def test_empty_duplicate_and_inactive_items(client):
    for items in [
        [],
        [{"product_id": 1, "quantity": 1}] * 2,
        [{"product_id": 999, "quantity": 1}],
    ]:
        assert (
            client.post("/api/orders", json=order_data(items=items)).status_code == 400
        )
    client.put(
        "/api/products/1",
        json={
            "name": "Keyboard",
            "product_code": "KEY",
            "category": "Accessories",
            "price": 1500,
            "status": "Inactive",
        },
    )
    assert client.post("/api/orders", json=order_data()).status_code == 400


def test_confirmation_cancellation_idempotency(client, app):
    order_id = create(client)
    assert stock(app) == 20
    for _ in range(2):
        assert client.post(f"/api/orders/{order_id}/confirm").status_code == 200
    assert stock(app) == 18
    for _ in range(2):
        assert client.post(f"/api/orders/{order_id}/cancel").status_code == 200
    assert stock(app) == 20
    assert client.post(f"/api/orders/{order_id}/confirm").status_code == 409
    with Session(app.extensions["engine"]) as db:
        assert db.scalar(select(func.count()).select_from(StockMovement)) == 4


def test_insufficient_item_rolls_back_everything(client, app):
    order_id = create(
        client,
        items=[{"product_id": 1, "quantity": 2}, {"product_id": 2, "quantity": 51}],
    )
    assert client.post(f"/api/orders/{order_id}/confirm").status_code == 409
    assert stock(app) == 20 and stock(app, 2) == 50
    assert client.get(f"/api/orders/{order_id}").json["status"] == "Draft"
    with Session(app.extensions["engine"]) as db:
        assert db.scalar(select(func.count()).select_from(StockMovement)) == 0


def test_draft_cancel_and_read_only(client, app):
    order_id = create(client)
    client.post(f"/api/orders/{order_id}/cancel")
    assert stock(app) == 20
    assert client.put(f"/api/orders/{order_id}", json=order_data()).status_code == 409
    order_id = create(client)
    client.post(f"/api/orders/{order_id}/confirm")
    assert client.put(f"/api/orders/{order_id}", json=order_data()).status_code == 409


def test_prices_stay_saved_on_edit(client):
    order_id = create(client)
    client.put(
        "/api/products/1",
        json={
            "name": "Keyboard",
            "product_code": "KEY",
            "category": "Accessories",
            "price": 2000,
            "status": "Active",
        },
    )
    result = client.put(f"/api/orders/{order_id}", json=order_data())
    assert result.status_code == 200, result.json
    assert result.json["items"][0]["rate"] == "1500.00"


def test_permissions_and_csrf(app, client):
    sales = login_client(app, 2)
    other = login_client(app, 3)
    order_id = create(sales)
    for method, path in [
        ("get", f"/api/orders/{order_id}"),
        ("post", f"/api/orders/{order_id}/confirm"),
        ("post", f"/api/orders/{order_id}/cancel"),
    ]:
        assert getattr(other, method)(path).status_code == 403
    assert other.get("/api/orders").json["items"] == []
    assert sales.post("/api/products", json={}).status_code == 403
    assert sales.get("/api/reports/customers").status_code == 403
    assert sales.post("/api/products/import", data={}).status_code == 403
    assert app.test_client().get("/api/orders").status_code == 401
    assert (
        client.post(
            "/api/orders", json=order_data(), headers={"X-CSRF-Token": "wrong"}
        ).status_code
        == 403
    )


def upload(client, rows):
    data = "product_code,product_name,category,price,stock_quantity,status\n" + rows
    return client.post(
        "/api/products/import",
        data={"file": (io.BytesIO(data.encode()), "products.csv")},
    )


@pytest.mark.parametrize(
    "bad_row",
    [
        "NEW2,Wrong,Office,-1,2,Active",
        "NEW,Duplicate,Office,20,1,Active",
        "KEY,Existing,Office,20,1,Active",
        "BAD,Wrong,Office,20,1.5,Active",
        "BAD,Wrong,Office,20,1,Unknown",
    ],
)
def test_csv_rollback(client, app, bad_row):
    result = upload(client, "NEW,New,Office,25,5,Active\n" + bad_row + "\n")
    assert result.status_code == 400
    assert result.json["details"][0]["row"] == 3
    with Session(app.extensions["engine"]) as db:
        assert db.scalar(select(func.count()).select_from(Product)) == 2
        assert db.scalar(select(func.count()).select_from(StockMovement)) == 0


def test_csv_success_and_adjustment(client, app):
    assert upload(client, "NEW,New,Office,25,5,Active\n").json["imported"] == 1
    assert (
        client.post(
            "/api/products/1/adjust", json={"quantity_change": -21, "reason": "Count"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/products/1/adjust", json={"quantity_change": 2, "reason": ""}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/products/1/adjust", json={"quantity_change": 2, "reason": "Count"}
        ).status_code
        == 200
    )
    assert stock(app) == 22


def test_reports_zero_customers_and_no_double_count(client):
    order_id = create(client)
    create(client)  # draft excluded
    client.post(f"/api/orders/{order_id}/confirm")
    rows = client.get("/api/reports/customers?start=2026-11-01&end=2026-11-30").json[
        "items"
    ]
    assert rows == [
        {"name": "Buyer", "orders": "1", "sales": "4050.00"},
        {"name": "Zero buyer", "orders": "0", "sales": "0.00"},
    ]
    assert all(
        row["orders"] == "0"
        for row in client.get("/api/reports/customers?start=2027-01-01").json["items"]
    )
    assert (
        client.get("/api/reports/products").json["items"][0]["gross_value"] == "3000.00"
    )
    assert (
        client.get("/api/reports/low-stock?threshold=19").json["items"][0][
            "product_code"
        ]
        == "KEY"
    )
    assert len(client.get("/api/reports/movements").json["items"]) == 2


def test_deletion_constraints_and_api_errors(client):
    create(client)
    assert client.delete("/api/customers/1").status_code == 409
    assert client.delete("/api/products/1").status_code == 409
    assert client.get("/api/orders/999").status_code == 404
    assert client.post("/api/orders", json=[]).status_code == 400
    assert client.get("/api/products?page_size=0").status_code == 400
    assert client.get("/api/products?search=KEY").json["total"] == 1
    assert "password_hash" not in client.get("/api/session").json["user"]


def test_debugging():
    assert calculate_total(
        [{"qty": 2, "rate": 100}, {"qty": 3, "rate": 50}]
    ) == Decimal("350.00")
    assert calculate_total([]) == Decimal("0.00")
    for row in [
        {"qty": 2},
        {"rate": 3},
        {"qty": 0, "rate": 2},
        {"qty": 1, "rate": -2},
        {"qty": 1, "rate": "NaN"},
    ]:
        with pytest.raises(ValueError):
            calculate_total([row])


def test_mysql_concurrent_confirmations(app, client):
    if app.extensions["engine"].dialect.name != "mysql":
        pytest.skip("Requires MySQL row locks. Set TEST_DATABASE_URL.")
    first = create(client, items=[{"product_id": 1, "quantity": 15}])
    second = create(client, items=[{"product_id": 1, "quantity": 15}])
    clients = [login_client(app, 1), login_client(app, 1)]
    barrier = Barrier(2)

    def confirm(pair):
        own_client, order_id = pair
        barrier.wait(timeout=10)
        return own_client.post(f"/api/orders/{order_id}/confirm").status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(confirm, zip(clients, [first, second])))
    assert sorted(results) == [200, 409]
    assert stock(app) == 5


@pytest.mark.parametrize("action,expected_stock", [("confirm", 18), ("cancel", 20)])
def test_mysql_concurrent_repeated_action(app, client, action, expected_stock):
    if app.extensions["engine"].dialect.name != "mysql":
        pytest.skip("Requires MySQL row locks. Set TEST_DATABASE_URL.")
    order_id = create(client)
    if action == "cancel":
        client.post(f"/api/orders/{order_id}/confirm")
    clients = [login_client(app, 1), login_client(app, 1)]
    barrier = Barrier(2)

    def perform(own_client):
        barrier.wait(timeout=10)
        return own_client.post(f"/api/orders/{order_id}/{action}").status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(perform, clients)) == [200, 200]
    assert stock(app) == expected_stock
