# Sales order page 

import json

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.datastructures import MultiDict

from app import models
from app.decorators import login_required, current_user
from app.services import order_service

bp = Blueprint("orders", __name__, url_prefix="/orders")

STATUSES = ("Draft", "Confirmed", "Cancelled")


def get_order_or_abort(order_id):
    order = models.get_order(order_id, current_user())
    if order is None:
        if models.order_exists(order_id):
            abort(403)
        abort(404)
    return order


def render_order_form(mode, order, form, errors, status_code=200):
    products = models.list_products(status="active")
    customers = models.list_customers(status="active")

    # Names only: price and stock are fetched from /api/products/<id> when a product is chosen.
    products_for_js = []
    for p in products:
        products_for_js.append({
            "id": p["id"],
            "product_code": p["product_code"],
            "name": p["name"],
        })

    rows = []
    if form is not None:
        product_ids = form.getlist("product_id")
        quantities = form.getlist("quantity")
        for index in range(len(product_ids)):
            rows.append({
                "product_id": product_ids[index],
                "quantity": quantities[index] if index < len(quantities) else "",
            })

    return render_template(
        "orders/form.html",
        mode=mode,
        order=order,
        form=form,
        errors=errors,
        customers=customers,
        products=products,
        products_json=json.dumps(products_for_js),
        rows_json=json.dumps(rows),
    ), status_code


@bp.route("/")
@login_required
def index():
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    if status not in STATUSES:
        status = ""

    orders = models.list_orders(current_user(), search=search, status=status)
    return render_template(
        "orders/index.html",
        orders=orders,
        search=search,
        status=status,
        statuses=STATUSES,
        is_admin=session.get("user_role") == "admin",
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        clean_order, errors = order_service.validate_order_form(request.form)
        if errors:
            return render_order_form("new", None, request.form, errors, 400)

        order_id = order_service.create_order(clean_order, session["user_id"])
        flash("Order created as a draft.", "success")
        return redirect(url_for("orders.detail", order_id=order_id))

    return render_order_form("new", None, None, [])


@bp.route("/<int:order_id>")
@login_required
def detail(order_id):
    order = get_order_or_abort(order_id)
    items = models.list_order_items(order_id)
    return render_template("orders/detail.html", order=order, items=items)


@bp.route("/<int:order_id>/edit", methods=["GET", "POST"])
@login_required
def edit(order_id):
    order = get_order_or_abort(order_id)

    if order["status"] != "Draft":
        flash("Only Draft orders can be edited.", "error")
        return redirect(url_for("orders.detail", order_id=order_id))

    if request.method == "POST":
        clean_order, errors = order_service.validate_order_form(request.form)
        if errors:
            return render_order_form("edit", order, request.form, errors, 400)

        order_service.update_draft_order(order, clean_order)
        flash("Order %s was updated." % order["order_number"], "success")
        return redirect(url_for("orders.detail", order_id=order_id))

    # Pre-fill from the saved order using the same MultiDict shape a submitted form has.
    items = models.list_order_items(order_id)
    saved_form = MultiDict()
    saved_form.add("customer_id", str(order["customer_id"]))
    saved_form.add("order_date", order["order_date"].isoformat())
    saved_form.add("discount_percentage", str(order["discount_percentage"]))
    for item in items:
        saved_form.add("product_id", str(item["product_id"]))
        saved_form.add("quantity", str(item["quantity"]))

    return render_order_form("edit", order, saved_form, [])


@bp.route("/<int:order_id>/confirm", methods=["POST"])
@login_required
def confirm(order_id):
    get_order_or_abort(order_id)  # 403 / 404 for orders the user may not see
    ok, message = order_service.confirm_order(order_id, current_user())
    flash(message, "success" if ok else "error")
    return redirect(url_for("orders.detail", order_id=order_id))


@bp.route("/<int:order_id>/cancel", methods=["POST"])
@login_required
def cancel(order_id):
    get_order_or_abort(order_id)
    ok, message = order_service.cancel_order(order_id, current_user())
    flash(message, "success" if ok else "error")
    return redirect(url_for("orders.detail", order_id=order_id))
