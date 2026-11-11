"""Sales order pages. Placeholder route for now."""

from flask import Blueprint, render_template

from app.decorators import login_required

bp = Blueprint("orders", __name__, url_prefix="/orders")


@bp.route("/")
@login_required
def index():
    return render_template("placeholder.html", title="Orders")
