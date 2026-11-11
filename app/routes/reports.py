"""Reports. Admin only."""

from flask import Blueprint, render_template, request

from app import models
from app.decorators import admin_required
from app.services import report_service

bp = Blueprint("reports", __name__, url_prefix="/reports")


@bp.route("/")
@admin_required
def index():
    return render_template("reports/index.html")


@bp.route("/customer-sales")
@admin_required
def customer_sales():
    filters, errors = report_service.parse_date_range(request.args)
    rows = []
    if not errors:
        rows = report_service.customer_sales(filters["date_from"], filters["date_to"])

    # Grand totals for the footer, summed in Python from the Decimal values.
    total_orders = sum(row["order_count"] for row in rows)
    total_sales = sum(row["total_sales"] for row in rows)

    return render_template(
        "reports/customer_sales.html",
        rows=rows, errors=errors, args=request.args,
        total_orders=total_orders, total_sales=total_sales,
    )


@bp.route("/product-sales")
@admin_required
def product_sales():
    filters, errors = report_service.parse_date_range(request.args)
    rows = []
    if not errors:
        rows = report_service.product_sales(filters["date_from"], filters["date_to"])

    total_qty = sum(row["qty_sold"] for row in rows)
    total_value = sum(row["gross_value"] for row in rows)

    return render_template(
        "reports/product_sales.html",
        rows=rows, errors=errors, args=request.args,
        total_qty=total_qty, total_value=total_value,
    )


@bp.route("/low-stock")
@admin_required
def low_stock():
    threshold, errors = report_service.parse_threshold(request.args.get("threshold"))
    rows = report_service.low_stock(threshold)
    return render_template(
        "reports/low_stock.html",
        rows=rows, errors=errors, threshold=threshold,
    )


@bp.route("/stock-movements")
@admin_required
def stock_movements():
    filters, errors = report_service.parse_movement_filters(request.args)
    rows = []
    if not errors:
        rows = report_service.stock_movements(filters)

    return render_template(
        "reports/stock_movements.html",
        rows=rows, errors=errors, args=request.args,
        products=models.list_products(status="all"),
        movement_types=report_service.MOVEMENT_TYPES,
    )
