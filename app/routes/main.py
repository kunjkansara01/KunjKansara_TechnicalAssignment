#Home page 

from flask import Blueprint, render_template

from app.decorators import login_required

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def home():
    return render_template("home.html")
