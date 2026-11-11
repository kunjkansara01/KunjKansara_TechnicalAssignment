"""Application factory: builds and configures the Flask app."""

from flask import Flask, jsonify, render_template

from app.config import Config
from app import db
from app.decorators import is_api_request


def create_app(test_config=None):
    app = Flask(__name__)

    app.config.from_object(Config)

    # Tests can pass a dictionary to override settings (e.g. a test database).
    if test_config is not None:
        app.config.update(test_config)

    db.init_app(app)

    from app.routes import main, auth, customers, products, orders, reports, api

    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(customers.bp)
    app.register_blueprint(products.bp)
    app.register_blueprint(orders.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(api.bp)

    register_error_handlers(app)
    register_template_filters(app)

    return app


def register_template_filters(app):
    """Small helpers usable inside templates, e.g. {{ order.grand_total|money }}."""

    def money(value):
        # Thousands separator and exactly two decimals: 12500 -> 12,500.00
        if value is None:
            return ""
        return "{:,.2f}".format(value)

    app.jinja_env.filters["money"] = money


def register_error_handlers(app):
    """Return friendly error pages (or JSON for /api/) instead of tracebacks."""

    def render_error(code, message):
        if is_api_request():
            # Same shape as every other API error: {"ok": false, "message": ...}
            if code == 404:
                message = "Not found."
            return jsonify({"ok": False, "message": message}), code
        return render_template("error.html", code=code, message=message), code

    @app.errorhandler(401)
    def unauthorized(error):
        return render_error(401, "Authentication required.")

    @app.errorhandler(403)
    def forbidden(error):
        return render_error(403, "You do not have permission to do that.")

    @app.errorhandler(404)
    def not_found(error):
        return render_error(404, "Page not found.")

    @app.errorhandler(405)
    def method_not_allowed(error):
        return render_error(405, "Method not allowed.")

    @app.errorhandler(413)
    def too_large(error):
        return render_error(413, "The uploaded file is too large (limit 2 MB).")

    @app.errorhandler(500)
    def internal_error(error):
        # Log the traceback server-side; the client only ever gets a generic message.
        app.logger.exception("Unhandled server error")
        return render_error(500, "Something went wrong. Please try again.")
