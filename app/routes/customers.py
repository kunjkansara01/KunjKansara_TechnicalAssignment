"""Customer pages: everyone can list; create, edit, deactivate and delete are admin only."""

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from app import models
from app.decorators import login_required, admin_required
from app.services import customer_service

bp = Blueprint("customers", __name__, url_prefix="/customers")


def get_customer_or_404(customer_id):
    customer = models.get_customer_by_id(customer_id)
    if customer is None:
        abort(404)
    return customer


@bp.route("/")
@login_required
def index():
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "active")

    # Sales users are not allowed to see inactive customers at all.
    is_admin = session.get("user_role") == "admin"
    if not is_admin:
        status = "active"
    elif status not in ("active", "inactive", "all"):
        status = "active"

    customers = models.list_customers(search=search, status=status)
    return render_template(
        "customers/index.html",
        customers=customers,
        search=search,
        status=status,
        is_admin=is_admin,
    )


@bp.route("/new", methods=["GET", "POST"])
@admin_required
def create():
    if request.method == "POST":
        clean_data, errors = customer_service.validate_customer_form(request.form)
        if errors:
            return render_template(
                "customers/form.html", customer=request.form, errors=errors, mode="new"
            ), 400

        customer_service.create_customer(clean_data)
        flash("Customer '%s' was created." % clean_data["name"], "success")
        return redirect(url_for("customers.index"))

    return render_template("customers/form.html", customer={}, errors=[], mode="new")


@bp.route("/<int:customer_id>/edit", methods=["GET", "POST"])
@admin_required
def edit(customer_id):
    customer = get_customer_or_404(customer_id)

    if request.method == "POST":
        clean_data, errors = customer_service.validate_customer_form(request.form)
        if errors:
            # Merge the typed values over the saved ones so the form keeps the id.
            typed = dict(customer)
            typed.update(request.form)
            return render_template(
                "customers/form.html", customer=typed, errors=errors, mode="edit"
            ), 400

        customer_service.update_customer(customer_id, clean_data)
        flash("Customer '%s' was updated." % clean_data["name"], "success")
        return redirect(url_for("customers.index"))

    return render_template("customers/form.html", customer=customer, errors=[], mode="edit")


@bp.route("/<int:customer_id>/deactivate", methods=["POST"])
@admin_required
def deactivate(customer_id):
    customer = get_customer_or_404(customer_id)
    customer_service.set_active(customer_id, False)
    flash("Customer '%s' was deactivated." % customer["name"], "success")
    return redirect(url_for("customers.index", status=request.form.get("status", "active")))


@bp.route("/<int:customer_id>/activate", methods=["POST"])
@admin_required
def activate(customer_id):
    customer = get_customer_or_404(customer_id)
    customer_service.set_active(customer_id, True)
    flash("Customer '%s' was activated." % customer["name"], "success")
    return redirect(url_for("customers.index", status=request.form.get("status", "active")))


@bp.route("/<int:customer_id>/delete", methods=["POST"])
@admin_required
def delete(customer_id):
    customer = get_customer_or_404(customer_id)
    ok, message = customer_service.delete_customer(customer)
    flash(message, "success" if ok else "error")
    return redirect(url_for("customers.index", status=request.form.get("status", "active")))
