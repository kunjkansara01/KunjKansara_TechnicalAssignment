"""Route decorators that enforce login and admin role.

Usage inside a blueprint:

    @bp.route("/")
    @login_required
    def index(): ...

    @bp.route("/new")
    @admin_required
    def create(): ...

Rules
  * Not logged in  -> web page: redirect to login;   API: 401 JSON
  * Not an admin   -> web page: 403 error page;      API: 403 JSON
"""

from functools import wraps

from flask import abort, flash, jsonify, redirect, request, session, url_for


def is_api_request():
    """API routes live under /api/ and must get JSON, never a redirect."""
    return request.path.startswith("/api/")


def current_user():
    """Return the logged-in user's details stored in the session, or None."""
    if "user_id" not in session:
        return None
    return {
        "id": session["user_id"],
        "name": session["user_name"],
        "role": session["user_role"],
    }


def login_required(view):
    @wraps(view)  # keeps the original function name so url_for still works
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            if is_api_request():
                return jsonify({"error": "Authentication required"}), 401
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        # Step 1: must be logged in at all.
        if "user_id" not in session:
            if is_api_request():
                return jsonify({"error": "Authentication required"}), 401
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login"))

        # Step 2: must have the admin role.
        if session.get("user_role") != "admin":
            if is_api_request():
                return jsonify({"error": "Admin access required"}), 403
            abort(403)

        return view(*args, **kwargs)

    return wrapped_view
