"""One MySQL connection per request, closed automatically when the request ends."""

import mysql.connector
from flask import current_app, g


def get_db():
    """Return the connection for the current request, opening it if needed."""
    if "db" not in g:
        g.db = mysql.connector.connect(
            host=current_app.config["DB_HOST"],
            port=current_app.config["DB_PORT"],
            user=current_app.config["DB_USER"],
            password=current_app.config["DB_PASSWORD"],
            database=current_app.config["DB_NAME"],
        )
    return g.db


def close_db(exception=None):
    """Close the connection at the end of the request, if one was opened."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    """Tell Flask to call close_db() after every request."""
    app.teardown_appcontext(close_db)
