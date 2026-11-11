"""JSON API under /api; reuses the same service functions as the web pages."""

from flask import Blueprint, jsonify, request, session
from werkzeug.datastructures import MultiDict

from app import models
from app.decorators import login_required, admin_required, current_user
from app.services import order_service

bp = Blueprint("api", __name__, url_prefix="/api")

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# helper functions for JSON responses
def error(message, status_code, errors=None):
    """Uniform error body: {"ok": false, "message": "...", "errors": [...]}"""
    body = {"ok": False, "message": message}
    if errors:
        body["errors"] = errors
    return jsonify(body), status_code


def product_to_dict(product):
    return {
        "id": product["id"],
        "product_code": product["product_code"],
        "name": product["name"],
        "category": product["category"],
        "price": str(product["price"]),          # Decimal -> string keeps 2 dp exact
        "stock_quantity": product["stock_quantity"],
        "is_active": bool(product["is_active"]),
    }


def order_to_dict(order, items):
    return {
        "id": order["id"],
        "order_number": order["order_number"],
        "status": order["status"],
        "order_date": order["order_date"].isoformat(),
        "customer": {"id": order["customer_id"], "name": order["customer_name"]},
        "created_by": {"id": order["created_by"], "name": order["created_by_name"]},
        "discount_percentage": str(order["discount_percentage"]),
        "subtotal": str(order["subtotal"]),
        "discount_amount": str(order["discount_amount"]),
        "grand_total": str(order["grand_total"]),
        "items": [
            {
                "product_id": item["product_id"],
                "product_code": item["product_code"],
                "product_name": item["product_name"],
                "quantity": item["quantity"],
                "rate": str(item["rate"]),
                "amount": str(item["amount"]),
            }
            for item in items
        ],
    }


def parse_positive_int(text, default):
    """Query-string helper: '3' -> 3; anything else -> default."""
    if text is None or not str(text).isdigit() or int(text) < 1:
        return default
    return int(text)

# ping and user info endpoints for testing and debugging
@bp.route("/ping")
@login_required
def ping():
    return jsonify({"status": "ok"})


@bp.route("/me")
@login_required
def me():
    return jsonify({
        "id": session["user_id"],
        "name": session["user_name"],
        "role": session["user_role"],
    })


@bp.route("/admin/ping")
@admin_required
def admin_ping():
    # Exists so the admin-only rule (403 for sales) can be demonstrated.
    return jsonify({"status": "ok", "role": "admin"})


#product endpoints for the order form's JavaScript
@bp.route("/products")
@login_required
def product_list():
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    page = parse_positive_int(request.args.get("page"), 1)
    per_page = min(parse_positive_int(request.args.get("per_page"), DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE)

    total = models.count_products(search=search, category=category, status="active")
    products = models.list_products(
        search=search, category=category, status="active",
        limit=per_page, offset=(page - 1) * per_page,
    )

    return jsonify({
        "ok": True,
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": (total + per_page - 1) // per_page if total else 0,
        "items": [product_to_dict(p) for p in products],
    })


@bp.route("/products/<int:product_id>")
@login_required
def product_detail(product_id):
    product = models.get_product_by_id(product_id)

    # Sales users may not see inactive products at all.
    if product is None or (session.get("user_role") != "admin" and not product["is_active"]):
        return error("Product not found.", 404)

    body = product_to_dict(product)
    body["ok"] = True
    return jsonify(body)

# order endpoints for the order form's JavaScript

@bp.route("/orders", methods=["POST"])
@login_required
def create_order():
    """Create a Draft order from JSON, reusing the web form's validation unchanged."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("Request body must be a JSON object.", 400)

    form = MultiDict()
    form.add("customer_id", str(payload.get("customer_id", "")))
    form.add("order_date", str(payload.get("order_date", "")))
    form.add("discount_percentage", str(payload.get("discount_percentage", "0")))

    items = payload.get("items", [])
    if not isinstance(items, list):
        return error("'items' must be a list.", 400)
    for item in items:
        if not isinstance(item, dict):
            return error("Each item must be an object with product_id and quantity.", 400)
        form.add("product_id", str(item.get("product_id", "")))
        form.add("quantity", str(item.get("quantity", "")))

    clean_order, errors = order_service.validate_order_form(form)
    if errors:
        return error("Validation failed.", 400, errors)

    order_id = order_service.create_order(clean_order, session["user_id"])

    order = models.get_order(order_id, current_user())
    order_items = models.list_order_items(order_id)
    body = order_to_dict(order, order_items)
    body["ok"] = True
    return jsonify(body), 201


@bp.route("/orders/<int:order_id>")
@login_required
def get_order(order_id):
    """One order with its items. Another user's order -> 403, unknown id -> 404."""
    order = models.get_order(order_id, current_user())
    if order is None:
        if models.order_exists(order_id):
            return error(order_service.FORBIDDEN_MESSAGE, 403)
        return error(order_service.NOT_FOUND_MESSAGE, 404)

    body = order_to_dict(order, models.list_order_items(order_id))
    body["ok"] = True
    return jsonify(body)


def order_action_response(order_id, ok, message):
    """Shared JSON shape for confirm and cancel."""
    if not ok:
        if message == order_service.NOT_FOUND_MESSAGE:
            status_code = 404
        elif message == order_service.FORBIDDEN_MESSAGE:
            status_code = 403
        else:
            status_code = 409          # wrong status / insufficient stock
        return error(message, status_code)

    order = models.get_order(order_id, current_user())
    return jsonify({"ok": True, "message": message, "status": order["status"]})


@bp.route("/orders/<int:order_id>/confirm", methods=["POST"])
@login_required
def confirm_order(order_id):
    ok, message = order_service.confirm_order(order_id, current_user())
    return order_action_response(order_id, ok, message)


@bp.route("/orders/<int:order_id>/cancel", methods=["POST"])
@login_required
def cancel_order(order_id):
    ok, message = order_service.cancel_order(order_id, current_user())
    return order_action_response(order_id, ok, message)
