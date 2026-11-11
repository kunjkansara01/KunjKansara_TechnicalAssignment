"""login_required / admin_required. Web pages redirect or get 403; /api/ gets 401/403 JSON."""

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


def not_logged_in_response():
    """What to send when there is no user in the session."""
    if is_api_request():
        return jsonify({"ok": False, "message": "Authentication required"}), 401
    flash("Please log in to continue.", "error")
    return redirect(url_for("auth.login"))


def login_required(view):
    @wraps(view)  # keeps the original function name so url_for still works
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return not_logged_in_response()
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return not_logged_in_response()

        if session.get("user_role") != "admin":
            if is_api_request():
                return jsonify({"ok": False, "message": "Admin access required"}), 403
            abort(403)

        return view(*args, **kwargs)

    return wrapped_view
