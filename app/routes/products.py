"""Product / inventory pages. Placeholder route for now."""

from flask import Blueprint, render_template

from app.decorators import login_required

bp = Blueprint("products", __name__, url_prefix="/products")


@bp.route("/")
@login_required
def index():
    return render_template("placeholder.html", title="Products")
