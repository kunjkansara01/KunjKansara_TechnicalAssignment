"""JSON API used by the browser's JavaScript.

Every route here returns JSON. The decorators detect the /api/ prefix and
answer 401 / 403 as JSON instead of redirecting.
"""

from flask import Blueprint, jsonify, session

from app.decorators import login_required, admin_required

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.route("/ping")
@login_required
def ping():
    # Quick way to confirm the API blueprint and login check are wired up.
    return jsonify({"status": "ok"})


@bp.route("/me")
@login_required
def me():
    # Returns who is logged in. Handy for the front-end JavaScript.
    return jsonify({
        "id": session["user_id"],
        "name": session["user_name"],
        "role": session["user_role"],
    })


@bp.route("/admin/ping")
@admin_required
def admin_ping():
    # Exists so the admin-only rule can be demonstrated and tested.
    return jsonify({"status": "ok", "role": "admin"})
