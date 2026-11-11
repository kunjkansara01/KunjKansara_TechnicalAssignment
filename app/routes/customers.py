"""Customer pages. Placeholder route for now."""

from flask import Blueprint, render_template

from app.decorators import login_required

bp = Blueprint("customers", __name__, url_prefix="/customers")


@bp.route("/")
@login_required
def index():
    return render_template("placeholder.html", title="Customers")
