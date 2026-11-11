"""Sales order rules. All money is calculated here in Decimal; never trust totals from the browser."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import mysql.connector

from app import models
from app.db import get_db
from app.services.money import to_money

MAX_DISCOUNT = Decimal("20.00")
MYSQL_DUPLICATE_KEY = 1062


# ---- pure calculation (no database) ----

def calculate_totals(items, discount_percentage):
    """Set each item's amount (qty x rate) and return subtotal, discount_amount, grand_total."""
    subtotal = Decimal("0.00")
    for item in items:
        item["amount"] = to_money(Decimal(item["quantity"]) * item["rate"])
        subtotal += item["amount"]

    discount_amount = to_money(subtotal * discount_percentage / Decimal("100"))
    grand_total = to_money(subtotal - discount_amount)

    return {
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "grand_total": grand_total,
    }


# ---- Validation ----

def parse_discount(text):
    """Return the discount as a 2-place Decimal, or None if not a number."""
    text = (text or "").strip()
    if text == "":
        return Decimal("0.00")
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    if not value.is_finite():
        return None
    return to_money(value)


def parse_date(text):
    """Return a date for 'YYYY-MM-DD', today for blank, None if invalid."""
    text = (text or "").strip()
    if text == "":
        return date.today()
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def validate_order_form(form):
    """Validate the submitted form. Returns (clean_order, errors); totals are computed here."""
    errors = []

    # --- header -----------------------------------------------------------
    customer_id_text = (form.get("customer_id") or "").strip()
    customer = None
    if not customer_id_text.isdigit():
        errors.append("Please choose a customer.")
    else:
        customer = models.get_customer_by_id(int(customer_id_text))
        if customer is None or not customer["is_active"]:
            errors.append("The selected customer is not available.")

    order_date = parse_date(form.get("order_date"))
    if order_date is None:
        errors.append("Order date must be in YYYY-MM-DD format.")

    discount_percentage = parse_discount(form.get("discount_percentage"))
    if discount_percentage is None:
        errors.append("Discount must be a number.")
    elif discount_percentage < 0 or discount_percentage > MAX_DISCOUNT:
        errors.append("Discount must be between 0 and 20 percent.")

    # --- items ------------------------------------------------------------
    # The form sends parallel lists: product_id[] and quantity[].
    product_ids = form.getlist("product_id")
    quantities = form.getlist("quantity")

    items = []
    seen_product_ids = set()
    row_number = 0   # counts the rows the user actually filled in, for messages

    for index in range(len(product_ids)):
        product_id_text = (product_ids[index] or "").strip()
        quantity_text = (quantities[index] if index < len(quantities) else "").strip()

        # A completely blank row (unused template row) is simply skipped.
        if product_id_text == "" and quantity_text == "":
            continue

        row_number += 1

        if not product_id_text.isdigit():
            errors.append("Item %d: please choose a product." % row_number)
            continue
        product_id = int(product_id_text)

        if product_id in seen_product_ids:
            errors.append("Item %d: this product is already on the order. Change its quantity instead." % row_number)
            continue
        seen_product_ids.add(product_id)

        product = models.get_product_by_id(product_id)
        if product is None or not product["is_active"]:
            errors.append("Item %d: the selected product is not available." % row_number)
            continue

        if not quantity_text.isdigit() or int(quantity_text) <= 0:
            errors.append("Item %d (%s): quantity must be a whole number greater than zero."
                          % (row_number, product["product_code"]))
            continue

        items.append({
            "product_id": product["id"],
            "product_code": product["product_code"],
            "product_name": product["name"],
            "quantity": int(quantity_text),
            # Rate is the product's current DB price, frozen on the item; never taken from the browser.
            "rate": Decimal(product["price"]),
        })

    if not items and not any(message.startswith("Item ") for message in errors):
        errors.append("Add at least one item to the order.")

    if errors:
        return None, errors

    totals = calculate_totals(items, discount_percentage)

    clean_order = {
        "customer_id": customer["id"],
        "order_date": order_date,
        "discount_percentage": discount_percentage,
        "items": items,
        "subtotal": totals["subtotal"],
        "discount_amount": totals["discount_amount"],
        "grand_total": totals["grand_total"],
    }
    return clean_order, []


# ---- Order numbers ----

def next_order_number(year):
    """Return the next number in the SO-<year>-NNNN sequence."""
    highest = models.get_max_order_sequence_for_year(year)
    sequence = 1 if highest is None else int(highest) + 1
    return "SO-%d-%04d" % (year, sequence)


# ---- Create and update ----

def create_order(clean_order, user_id):
    """Insert header and items in one transaction; retry if another user took the order number."""
    db = get_db()
    year = clean_order["order_date"].year

    for attempt in range(3):
        order_number = next_order_number(year)
        try:
            order_id = models.insert_order(
                order_number,
                clean_order["customer_id"],
                clean_order["order_date"],
                clean_order["discount_percentage"],
                clean_order["subtotal"],
                clean_order["discount_amount"],
                clean_order["grand_total"],
                user_id,
            )
            for item in clean_order["items"]:
                models.insert_order_item(
                    order_id, item["product_id"], item["quantity"], item["rate"], item["amount"]
                )
            db.commit()
            return order_id
        except mysql.connector.IntegrityError as error:
            db.rollback()
            if error.errno == MYSQL_DUPLICATE_KEY and attempt < 2:
                continue  # someone else took that number; try the next one
            raise
        except mysql.connector.Error:
            db.rollback()
            raise


def update_draft_order(order, clean_order):
    """Replace a Draft's header and items in one transaction; rates refresh to current prices."""
    if order["status"] != "Draft":
        raise ValueError("Only Draft orders can be edited.")

    db = get_db()
    try:
        models.update_order_header(
            order["id"],
            clean_order["customer_id"],
            clean_order["order_date"],
            clean_order["discount_percentage"],
            clean_order["subtotal"],
            clean_order["discount_amount"],
            clean_order["grand_total"],
        )
        models.delete_order_items(order["id"])
        for item in clean_order["items"]:
            models.insert_order_item(
                order["id"], item["product_id"], item["quantity"], item["rate"], item["amount"]
            )
        db.commit()
    except mysql.connector.Error:
        db.rollback()
        raise


# ---- confirm and cancel: ONE transaction each ----
# Status is read from the locked order row, so a repeated request waits, then is refused.

NOT_FOUND_MESSAGE = "Order not found."
FORBIDDEN_MESSAGE = "You do not have access to this order."


def user_may_access(order_row, user):
    """Admin may touch any order; sales only their own."""
    return user["role"] == "admin" or order_row["created_by"] == user["id"]


def confirm_order(order_id, user):
    """Draft -> Confirmed. Locks order and product rows; any shortfall rolls everything back."""
    db = get_db()
    try:
        order = models.get_order_for_update(order_id)
        if order is None:
            db.rollback()
            return False, NOT_FOUND_MESSAGE
        if not user_may_access(order, user):
            db.rollback()
            return False, FORBIDDEN_MESSAGE

        if order["status"] != "Draft":
            db.rollback()
            return False, (
                "Order %s is already %s and cannot be confirmed."
                % (order["order_number"], order["status"])
            )

        items = models.list_order_items_with_products_for_update(order_id)
        if not items:
            db.rollback()
            return False, "Order %s has no items to confirm." % order["order_number"]

        shortfalls = []
        for item in items:
            if item["stock_quantity"] < item["quantity"]:
                shortfalls.append(
                    "%s: need %d, only %d in stock"
                    % (item["product_code"], item["quantity"], item["stock_quantity"])
                )

        if shortfalls:
            db.rollback()
            return False, (
                "Cannot confirm %s because of insufficient stock. %s."
                % (order["order_number"], "; ".join(shortfalls))
            )

        reason = "Order %s confirmed" % order["order_number"]
        for item in items:
            new_quantity = item["stock_quantity"] - item["quantity"]
            models.update_product_stock(item["product_id"], new_quantity)
            models.insert_stock_movement(
                item["product_id"], "order_confirm", -item["quantity"],
                order_id, reason, user["id"],
            )

        models.update_order_status(order_id, "Confirmed")
        db.commit()
    except mysql.connector.Error:
        db.rollback()
        raise

    return True, "Order %s confirmed. Stock has been deducted." % order["order_number"]


def cancel_order(order_id, user):
    """Draft/Confirmed -> Cancelled. A Confirmed order gets its stock restored in the same transaction."""
    db = get_db()
    try:
        order = models.get_order_for_update(order_id)
        if order is None:
            db.rollback()
            return False, NOT_FOUND_MESSAGE
        if not user_may_access(order, user):
            db.rollback()
            return False, FORBIDDEN_MESSAGE

        if order["status"] == "Cancelled":
            db.rollback()
            return False, "Order %s is already cancelled." % order["order_number"]

        if order["status"] == "Confirmed":
            items = models.list_order_items_with_products_for_update(order_id)
            reason = "Order %s cancelled" % order["order_number"]
            for item in items:
                new_quantity = item["stock_quantity"] + item["quantity"]
                models.update_product_stock(item["product_id"], new_quantity)
                models.insert_stock_movement(
                    item["product_id"], "order_cancel", item["quantity"],
                    order_id, reason, user["id"],
                )
            message = "Order %s cancelled. Stock has been restored." % order["order_number"]
        else:
            message = "Order %s cancelled." % order["order_number"]

        models.update_order_status(order_id, "Cancelled")
        db.commit()
    except mysql.connector.Error:
        db.rollback()
        raise

    return True, message
