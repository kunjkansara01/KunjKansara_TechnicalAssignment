"""Shared pytest fixtures.

The tests run against the real MySQL database named in .env, loaded with
sql/schema.sql and sql/seed.sql. Login tests rely on the two seeded users.
"""

import pytest

from app import create_app


@pytest.fixture
def app():
    app = create_app({"TESTING": True})
    return app


@pytest.fixture
def client(app):
    # A fake browser that sends requests to the app without a real server.
    return app.test_client()


def login(client, email, password):
    """Helper: submit the login form. Returns the response."""
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


@pytest.fixture
def admin_client(client):
    """A client already logged in as the seeded admin user."""
    login(client, "admin@example.com", "Admin@123")
    return client


@pytest.fixture
def sales_client(client):
    """A client already logged in as the seeded sales user."""
    login(client, "sales@example.com", "Sales@123")
    return client
