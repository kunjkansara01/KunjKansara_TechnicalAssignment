"""Shared fixtures. Tests run against a separate database rebuilt from schema.sql + seed.sql."""

import os

import mysql.connector
import pytest

from app import create_app
from app.config import Config

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_DIR = os.path.join(PROJECT_DIR, "sql")

TEST_DB_NAME = os.environ.get("TEST_DB_NAME", Config.DB_NAME + "_test")


def run_sql_file(connection, path):
    """Run a .sql file statement by statement (split on ';' after dropping comment lines)."""
    with open(path, encoding="utf-8") as f:
        lines = [line for line in f.read().splitlines() if not line.strip().startswith("--")]
    cursor = connection.cursor()
    for statement in "\n".join(lines).split(";"):
        if statement.strip():
            cursor.execute(statement)
    connection.commit()
    cursor.close()


@pytest.fixture(scope="session")
def test_database():
    """Create a fresh schema + seed in the test database once per pytest run."""
    if TEST_DB_NAME == Config.DB_NAME:
        pytest.exit("Refusing to run tests against the real database '%s'. "
                    "Set TEST_DB_NAME to a different name." % Config.DB_NAME)

    try:
        connection = mysql.connector.connect(
            host=Config.DB_HOST, port=Config.DB_PORT,
            user=Config.DB_USER, password=Config.DB_PASSWORD,
            database=TEST_DB_NAME,
        )
    except mysql.connector.Error as error:
        pytest.exit(
            "Cannot open test database '%s': %s\n"
            "Create it once as root:  mysql -u root -p -e \"source sql/setup_test_database.sql\""
            % (TEST_DB_NAME, error)
        )

    run_sql_file(connection, os.path.join(SQL_DIR, "schema.sql"))
    run_sql_file(connection, os.path.join(SQL_DIR, "seed.sql"))
    connection.close()
    return TEST_DB_NAME


@pytest.fixture
def app(test_database):
    """A Flask app pointed at the test database."""
    return create_app({"TESTING": True, "DB_NAME": test_database})


@pytest.fixture
def client(app):
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
    """Logged in as the seeded sales user. Shares one client with admin_client: never request both."""
    login(client, "sales@example.com", "Sales@123")
    return client
