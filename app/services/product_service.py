"""Product rules: validation, create, edit, activate, delete, stock adjustment."""

import mysql.connector

from app import models
from app.db import get_db
# Shared number parsing (also used by order_service and import_service).
from app.services.money import MAX_PRICE, parse_money, parse_whole_number  # noqa: F401


def validate_product_form(form, editing_product_id=None):
    """Validate the product form. Returns (clean_data, errors). Stock is ignored when editing."""
    product_code = (form.get("product_code") or "").strip().upper()
    name = (form.get("name") or "").strip()
    category = (form.get("category") or "").strip()
    price_text = form.get("price") or ""
    stock_text = form.get("stock_quantity") or "0"

    errors = []

    if product_code == "":
        errors.append("Product code is required.")
    elif len(product_code) > 50:
        errors.append("Product code must be 50 characters or fewer.")
    else:
        existing = models.get_product_by_code(product_code)
        if existing is not None and existing["id"] != editing_product_id:
            errors.append("Product code '%s' is already used by another product." % product_code)

    if name == "":
        errors.append("Name is required.")
    elif len(name) > 150:
        errors.append("Name must be 150 characters or fewer.")

    if len(category) > 100:
        errors.append("Category must be 100 characters or fewer.")

    price = parse_money(price_text)
    if price is None:
        errors.append("Price must be a number.")
    elif price < 0:
        errors.append("Price cannot be negative.")
    elif price > MAX_PRICE:
        errors.append("Price is too large.")

    stock_quantity = 0
    if editing_product_id is None:
        stock_quantity = parse_whole_number(stock_text)
        if stock_quantity is None:
            errors.append("Opening stock must be a whole number.")
        elif stock_quantity < 0:
            errors.append("Opening stock cannot be negative.")

    clean_data = {
        "product_code": product_code,
        "name": name,
        "category": category if category != "" else None,
        "price": price,
        "stock_quantity": stock_quantity,
    }
    return clean_data, errors


def create_product(clean_data, user_id):
    """Insert the product and its opening movement in one transaction so stock matches the ledger."""
    db = get_db()
    try:
        product_id = models.insert_product(
            clean_data["product_code"], clean_data["name"], clean_data["category"],
            clean_data["price"], clean_data["stock_quantity"],
        )
        if clean_data["stock_quantity"] > 0:
            models.insert_stock_movement(
                product_id, "opening", clean_data["stock_quantity"],
                None, "Opening stock", user_id,
            )
        db.commit()
    except mysql.connector.Error:
        db.rollback()
        raise
    return product_id


def update_product(product_id, clean_data):
    models.update_product(
        product_id,
        clean_data["product_code"], clean_data["name"], clean_data["category"], clean_data["price"],
    )
    get_db().commit()


def set_active(product_id, is_active):
    models.set_product_active(product_id, is_active)
    get_db().commit()


def delete_product(product):
    """Delete unless order lines or stock movements reference it. Returns (ok, message)."""
    order_lines = models.count_order_items_for_product(product["id"])
    movements = models.count_stock_movements_for_product(product["id"])

    if order_lines > 0 or movements > 0:
        return False, (
            "%s cannot be deleted because it is referenced by %d order line(s) and "
            "%d stock movement(s). Deactivate the product instead."
            % (product["name"], order_lines, movements)
        )

    db = get_db()
    try:
        models.delete_product(product["id"])
        db.commit()
    except mysql.connector.IntegrityError:
        db.rollback()
        return False, (
            "%s cannot be deleted because other records reference it. "
            "Deactivate the product instead." % product["name"]
        )

    return True, "%s was deleted." % product["name"]


def validate_adjustment_form(form):
    """Validate the Adjust Stock form. Returns (quantity_change, reason, errors). Reason is mandatory."""
    direction = (form.get("direction") or "").strip()
    quantity = parse_whole_number(form.get("quantity") or "")
    reason = (form.get("reason") or "").strip()

    errors = []

    if direction not in ("in", "out"):
        errors.append("Choose whether stock is coming in or going out.")

    if quantity is None:
        errors.append("Quantity must be a whole number.")
    elif quantity <= 0:
        errors.append("Quantity must be greater than zero.")

    if reason == "":
        errors.append("Reason is required.")
    elif len(reason) > 255:
        errors.append("Reason must be 255 characters or fewer.")

    quantity_change = None
    if not errors:
        quantity_change = quantity if direction == "in" else -quantity

    return quantity_change, reason, errors


def adjust_stock(product_id, quantity_change, reason, user_id):
    """Manual stock change in one transaction: row locked FOR UPDATE, never goes below zero."""
    db = get_db()
    try:
        product = models.get_product_by_id_for_update(product_id)
        if product is None:
            db.rollback()
            return False, "Product not found.", None

        new_quantity = product["stock_quantity"] + quantity_change
        if new_quantity < 0:
            db.rollback()
            return False, (
                "Cannot remove %d units: only %d in stock for %s."
                % (-quantity_change, product["stock_quantity"], product["name"])
            ), product["stock_quantity"]

        models.update_product_stock(product_id, new_quantity)
        models.insert_stock_movement(
            product_id, "adjustment", quantity_change, None, reason, user_id
        )
        db.commit()
    except mysql.connector.Error:
        db.rollback()
        raise

    return True, (
        "Stock for %s changed by %+d. New quantity: %d."
        % (product["name"], quantity_change, new_quantity)
    ), new_quantity
