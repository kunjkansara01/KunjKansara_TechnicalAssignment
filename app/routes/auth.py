"""Login and logout."""

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.services import auth_service

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/login", methods=["GET", "POST"])
def login():
    # Already logged in? Go straight to the home page.
    if "user_id" in session:
        return redirect(url_for("main.home"))

    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")

        user = auth_service.authenticate(email, password)

        if user is None:
            # One generic message on purpose: never reveal whether the email
            # exists or the password was wrong.
            flash("Invalid email or password.", "error")
            # Re-render with the typed email so the user does not retype it.
            return render_template("auth/login.html", email=email), 401

        # Successful login: start a fresh session and store only what the
        # app needs on every request. Never store the password or its hash.
        session.clear()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_role"] = user["role"]

        flash("Welcome, %s." % user["name"], "success")
        return redirect(url_for("main.home"))

    return render_template("auth/login.html", email="")


@bp.route("/logout", methods=["POST"])
def logout():
    # POST only, triggered by the Logout button in the nav bar, so a plain
    # link in an email or another site cannot log the user out.
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
