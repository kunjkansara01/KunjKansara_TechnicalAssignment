"""Login and logout."""

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.services import auth_service

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("main.home"))

    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")

        user = auth_service.authenticate(email, password)

        if user is None:
            # Generic message: never reveal whether the email exists.
            flash("Invalid email or password.", "error")
            return render_template("auth/login.html", email=email), 401

        session.clear()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_role"] = user["role"]

        flash("Welcome, %s." % user["name"], "success")
        return redirect(url_for("main.home"))

    return render_template("auth/login.html", email="")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
