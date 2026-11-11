"""Report filter parsing. Reports are read-only, so no transactions here."""

from datetime import datetime

from app import models

MOVEMENT_TYPES = ("opening", "order_confirm", "order_cancel", "adjustment")
DEFAULT_LOW_STOCK_THRESHOLD = 10


def parse_optional_date(text, label):
    """'' -> (None, None); 'YYYY-MM-DD' -> (date, None); bad -> (None, message)."""
    text = (text or "").strip()
    if text == "":
        return None, None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date(), None
    except ValueError:
        return None, "%s must be in YYYY-MM-DD format." % label


def parse_date_range(args):
    """Read date_from / date_to from the query string. Returns (filters, errors)."""
    errors = []
    date_from, error = parse_optional_date(args.get("date_from"), "From date")
    if error:
        errors.append(error)
    date_to, error = parse_optional_date(args.get("date_to"), "To date")
    if error:
        errors.append(error)

    if date_from and date_to and date_from > date_to:
        errors.append("From date must not be after To date.")

    return {"date_from": date_from, "date_to": date_to}, errors


def parse_threshold(text):
    """Low-stock threshold: whole number >= 0, default 10."""
    text = (text or "").strip()
    if text == "":
        return DEFAULT_LOW_STOCK_THRESHOLD, []
    if not text.isdigit():
        return DEFAULT_LOW_STOCK_THRESHOLD, ["Threshold must be a whole number of 0 or more."]
    return int(text), []


def parse_movement_filters(args):
    """Filters for the stock movement history."""
    filters, errors = parse_date_range(args)

    product_text = (args.get("product_id") or "").strip()
    filters["product_id"] = int(product_text) if product_text.isdigit() else None

    movement_type = (args.get("movement_type") or "").strip()
    if movement_type and movement_type not in MOVEMENT_TYPES:
        errors.append("Unknown movement type.")
        movement_type = ""
    filters["movement_type"] = movement_type

    return filters, errors


# Thin wrappers so routes talk to the service, not to models directly.

def customer_sales(date_from, date_to):
    return models.report_customer_sales(date_from, date_to)


def product_sales(date_from, date_to):
    return models.report_product_sales(date_from, date_to)


def low_stock(threshold):
    return models.report_low_stock(threshold)


def stock_movements(filters):
    return models.report_stock_movements(
        product_id=filters["product_id"],
        movement_type=filters["movement_type"],
        date_from=filters["date_from"],
        date_to=filters["date_to"],
    )
