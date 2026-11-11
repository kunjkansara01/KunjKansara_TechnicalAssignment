"""Application factory.

Flask recommends building the app inside a function (the "factory") instead of
at import time. This lets tests create a fresh app with different settings.
"""

from flask import Flask, jsonify, render_template, request

from app.config import Config
from app import db


def create_app(test_config=None):
    app = Flask(__name__)

    # Load settings from the Config class (which reads the .env file).
    app.config.from_object(Config)

    # Tests can pass a dictionary to override settings (e.g. a test database).
    if test_config is not None:
        app.config.update(test_config)

    # Let db.py register its "close connection after each request" hook.
    db.init_app(app)

    # Register every blueprint. Each blueprint is one feature area.
    from app.routes import main, auth, customers, products, orders, reports, api

    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(customers.bp)
    app.register_blueprint(products.bp)
    app.register_blueprint(orders.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(api.bp)

    register_error_handlers(app)

    return app


def register_error_handlers(app):
    """Return friendly error pages (or JSON for /api/) instead of tracebacks."""

    def is_api_request():
        return request.path.startswith("/api/")

    def render_error(code, message):
        if is_api_request():
            return jsonify({"error": message}), code
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

    @app.errorhandler(500)
    def internal_error(error):
        # Write the real traceback to the server log for the developer.
        # The browser only ever sees this generic message.
        app.logger.exception("Unhandled server error")
        return render_error(500, "Something went wrong. Please try again.")
