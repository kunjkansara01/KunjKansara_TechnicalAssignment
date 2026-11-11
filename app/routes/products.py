"""Product pages: list and stock history for everyone; changes and CSV import are admin only."""

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from app import models
from app.decorators import login_required, admin_required
from app.services import product_service, import_service

bp = Blueprint("products", __name__, url_prefix="/products")


def get_product_or_404(product_id):
    product = models.get_product_by_id(product_id)
    if product is None:
        abort(404)
    return product


def list_url():
    """Back to the list, keeping the filters that were in the submitted form."""
    return url_for(
        "products.index",
        q=request.form.get("q", ""),
        category=request.form.get("category_filter", ""),
        status=request.form.get("status", "active"),
    )


@bp.route("/")
@login_required
def index():
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    status = request.args.get("status", "active")

    is_admin = session.get("user_role") == "admin"
    if not is_admin:
        status = "active"
    elif status not in ("active", "inactive", "all"):
        status = "active"

    products = models.list_products(search=search, category=category, status=status)
    categories = models.list_product_categories()
    return render_template(
        "products/index.html",
        products=products,
        categories=categories,
        search=search,
        category=category,
        status=status,
        is_admin=is_admin,
    )


@bp.route("/new", methods=["GET", "POST"])
@admin_required
def create():
    if request.method == "POST":
        clean_data, errors = product_service.validate_product_form(request.form)
        if errors:
            return render_template(
                "products/form.html", product=request.form, errors=errors, mode="new"
            ), 400

        product_service.create_product(clean_data, session["user_id"])
        flash("Product '%s' was created." % clean_data["name"], "success")
        return redirect(url_for("products.index"))

    return render_template("products/form.html", product={}, errors=[], mode="new")


@bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def edit(product_id):
    product = get_product_or_404(product_id)

    if request.method == "POST":
        clean_data, errors = product_service.validate_product_form(
            request.form, editing_product_id=product_id
        )
        if errors:
            typed = dict(product)
            typed.update(request.form)
            return render_template(
                "products/form.html", product=typed, errors=errors, mode="edit"
            ), 400

        product_service.update_product(product_id, clean_data)
        flash("Product '%s' was updated." % clean_data["name"], "success")
        return redirect(url_for("products.index"))

    return render_template("products/form.html", product=product, errors=[], mode="edit")


@bp.route("/<int:product_id>/deactivate", methods=["POST"])
@admin_required
def deactivate(product_id):
    product = get_product_or_404(product_id)
    product_service.set_active(product_id, False)
    flash("Product '%s' was deactivated." % product["name"], "success")
    return redirect(list_url())


@bp.route("/<int:product_id>/activate", methods=["POST"])
@admin_required
def activate(product_id):
    product = get_product_or_404(product_id)
    product_service.set_active(product_id, True)
    flash("Product '%s' was activated." % product["name"], "success")
    return redirect(list_url())


@bp.route("/<int:product_id>/delete", methods=["POST"])
@admin_required
def delete(product_id):
    product = get_product_or_404(product_id)
    ok, message = product_service.delete_product(product)
    flash(message, "success" if ok else "error")
    return redirect(list_url())


@bp.route("/<int:product_id>/adjust-stock", methods=["GET", "POST"])
@admin_required
def adjust_stock(product_id):
    product = get_product_or_404(product_id)

    if request.method == "POST":
        quantity_change, reason, errors = product_service.validate_adjustment_form(request.form)
        if errors:
            return render_template(
                "products/adjust_stock.html", product=product, form=request.form, errors=errors
            ), 400

        ok, message, new_quantity = product_service.adjust_stock(
            product_id, quantity_change, reason, session["user_id"]
        )
        if not ok:
            return render_template(
                "products/adjust_stock.html", product=product, form=request.form, errors=[message]
            ), 400

        flash(message, "success")
        return redirect(url_for("products.movements", product_id=product_id))

    return render_template("products/adjust_stock.html", product=product, form={}, errors=[])


@bp.route("/<int:product_id>/movements")
@login_required
def movements(product_id):
    product = get_product_or_404(product_id)

    # Sales users may not look at inactive products.
    if session.get("user_role") != "admin" and not product["is_active"]:
        abort(404)

    rows = models.list_stock_movements_for_product(product_id)
    return render_template(
        "products/movements.html",
        product=product,
        movements=rows,
        is_admin=session.get("user_role") == "admin",
    )


@bp.route("/import", methods=["GET", "POST"])
@admin_required
def import_csv():
    """Upload a CSV of products. All rows are validated; all or nothing is saved."""
    if request.method == "POST":
        upload = request.files.get("file")
        if upload is None or upload.filename == "":
            return render_template(
                "products/import.html", errors=[{"row": "-", "message": "Choose a CSV file to upload."}],
                imported=None,
            ), 400

        imported, errors = import_service.process_upload(upload.read(), session["user_id"])
        if errors:
            return render_template(
                "products/import.html", errors=errors, imported=None, filename=upload.filename,
            ), 400

        flash("%d product(s) imported from %s." % (imported, upload.filename), "success")
        return redirect(url_for("products.index", status="all"))

    return render_template("products/import.html", errors=[], imported=None)
