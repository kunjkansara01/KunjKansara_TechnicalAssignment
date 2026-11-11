"""Reads settings from the .env file into a simple Config class.

Nothing secret is written here. Real values live in .env, which is ignored by
git. .env.example shows which keys are needed.
"""

import os

from dotenv import load_dotenv

# Read the .env file (if present) and put its keys into os.environ.
load_dotenv()


class Config:
    # Flask uses SECRET_KEY to sign the session cookie.
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-dotenv")

    # "1" turns on Flask's debugger (shows tracebacks in the browser).
    # Development only; defaults to off.
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

    # Session cookie hardening.
    SESSION_COOKIE_HTTPONLY = True      # JavaScript cannot read the cookie
    SESSION_COOKIE_SAMESITE = "Lax"     # not sent on cross-site POSTs

    # MySQL connection settings.
    DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.environ.get("DB_PORT", "3306"))
    DB_USER = os.environ.get("DB_USER", "root")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_NAME = os.environ.get("DB_NAME", "sales_inventory")
