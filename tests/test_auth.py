"""Login, logout, and the two access decorators."""

from tests.conftest import login


# ---------------------------------------------------------------------------
# Not logged in
# ---------------------------------------------------------------------------

def test_web_page_redirects_to_login_when_logged_out(client):
    response = client.get("/customers/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_home_redirects_to_login_when_logged_out(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_api_returns_401_json_when_logged_out(client):
    response = client.get("/api/ping")
    assert response.status_code == 401
    assert response.get_json() == {"error": "Authentication required"}


def test_login_page_loads(client):
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert b"Log in" in response.data


# ---------------------------------------------------------------------------
# Logging in
# ---------------------------------------------------------------------------

def test_login_with_correct_password_redirects_home(client):
    response = login(client, "admin@example.com", "Admin@123")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")

    # The session now lets us reach a protected page.
    response = client.get("/")
    assert response.status_code == 200
    assert b"Admin User" in response.data


def test_login_with_wrong_password_fails(client):
    response = login(client, "admin@example.com", "wrong-password")
    assert response.status_code == 401
    assert b"Invalid email or password." in response.data
    # The password must never be echoed back.
    assert b"wrong-password" not in response.data


def test_login_with_unknown_email_gives_same_message(client):
    response = login(client, "nobody@example.com", "Admin@123")
    assert response.status_code == 401
    assert b"Invalid email or password." in response.data


def test_login_email_is_case_insensitive(client):
    response = login(client, "  ADMIN@Example.com ", "Admin@123")
    assert response.status_code == 302


# ---------------------------------------------------------------------------
# Logging out
# ---------------------------------------------------------------------------

def test_logout_clears_session(admin_client):
    response = admin_client.post("/auth/logout")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]

    response = admin_client.get("/api/ping")
    assert response.status_code == 401


def test_logout_requires_post(admin_client):
    response = admin_client.get("/auth/logout")
    assert response.status_code == 405


# ---------------------------------------------------------------------------
# Role checks
# ---------------------------------------------------------------------------

def test_api_me_returns_logged_in_user(sales_client):
    response = sales_client.get("/api/me")
    assert response.status_code == 200
    data = response.get_json()
    assert data["name"] == "Sales User"
    assert data["role"] == "sales"
    assert "password" not in data
    assert "password_hash" not in data


def test_admin_route_allows_admin(admin_client):
    response = admin_client.get("/api/admin/ping")
    assert response.status_code == 200
    assert response.get_json()["role"] == "admin"


def test_admin_route_returns_403_json_for_sales_user(sales_client):
    response = sales_client.get("/api/admin/ping")
    assert response.status_code == 403
    assert response.get_json() == {"error": "Admin access required"}


def test_admin_route_returns_401_json_when_logged_out(client):
    response = client.get("/api/admin/ping")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Error pages
# ---------------------------------------------------------------------------

def test_unknown_web_page_gives_friendly_404(admin_client):
    response = admin_client.get("/does-not-exist")
    assert response.status_code == 404
    assert b"Page not found." in response.data
    assert b"Traceback" not in response.data


def test_unknown_api_route_gives_json_404(admin_client):
    response = admin_client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Page not found."}
