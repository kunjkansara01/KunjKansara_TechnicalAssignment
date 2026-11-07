import os
import pytest
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash
from app import create_app
from app.models import Base, Customer, Product, User


@pytest.fixture
def app(tmp_path):
    # A dedicated TEST_DATABASE_URL must point to a disposable database ending in _test.
    url = os.getenv("TEST_DATABASE_URL", f'sqlite:///{tmp_path / "test.db"}')
    if url.startswith("mysql"):
        from sqlalchemy.engine import make_url

        assert make_url(url).database.endswith(
            "_test"
        ), "Use a dedicated database ending in _test"
    app = create_app(
        {"TESTING": True, "SECRET_KEY": "test-session-key", "DATABASE_URL": url}
    )
    engine = app.extensions["engine"]
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as db, db.begin():
        for index, role in enumerate(["Admin", "Sales", "Sales"], 1):
            db.add(
                User(
                    id=index,
                    name=f"User {index}",
                    email=f"u{index}@example.test",
                    role=role,
                    password_hash=generate_password_hash("test-password"),
                )
            )
        db.add_all(
            [
                Customer(
                    id=1,
                    name="Buyer",
                    email="buyer@example.test",
                    mobile="123",
                    city="Mumbai",
                    status="Active",
                ),
                Customer(
                    id=2,
                    name="Zero buyer",
                    email="zero@example.test",
                    mobile="456",
                    city="Pune",
                    status="Active",
                ),
                Product(
                    id=1,
                    product_code="KEY",
                    name="Keyboard",
                    category="Accessories",
                    price=1500,
                    stock_quantity=20,
                    status="Active",
                ),
                Product(
                    id=2,
                    product_code="MOUSE",
                    name="Mouse",
                    category="Accessories",
                    price=500,
                    stock_quantity=50,
                    status="Active",
                ),
            ]
        )
    yield app
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(app):
    return login_client(app, 1)


def login_client(app, user_id):
    client = app.test_client()
    result = client.get("/api/session").json
    result = client.post(
        "/api/login",
        json={"email": f"u{user_id}@example.test", "password": "test-password"},
        headers={"X-CSRF-Token": result["csrf_token"]},
    )
    assert result.status_code == 200
    client.environ_base["HTTP_X_CSRF_TOKEN"] = result.json["csrf_token"]
    return client


def order_data(**overrides):
    return dict(
        {
            "customer_id": 1,
            "order_date": "2026-11-07",
            "discount_percentage": 10,
            "items": [
                {"product_id": 1, "quantity": 2},
                {"product_id": 2, "quantity": 3},
            ],
        },
        **overrides,
    )
