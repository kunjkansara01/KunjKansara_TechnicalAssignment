"""Report pages. Placeholder route for now."""

from flask import Blueprint, render_template

from app.decorators import login_required

bp = Blueprint("reports", __name__, url_prefix="/reports")


@bp.route("/")
@login_required
def index():
    return render_template("placeholder.html", title="Reports")
