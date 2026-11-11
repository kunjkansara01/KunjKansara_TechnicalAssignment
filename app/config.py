"""Settings read from .env. No secrets are hardcoded here."""

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    # Flask uses SECRET_KEY to sign the session cookie.
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-dotenv")

    # Debug mode shows tracebacks in the browser: development only, off by default.
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

    # Largest upload accepted (CSV import). Flask answers 413 above this.
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB

    SESSION_COOKIE_HTTPONLY = True      # JavaScript cannot read the cookie
    SESSION_COOKIE_SAMESITE = "Lax"     # not sent on cross-site POSTs

    DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.environ.get("DB_PORT", "3306"))
    DB_USER = os.environ.get("DB_USER", "sales_app")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_NAME = os.environ.get("DB_NAME", "sales_inventory")
