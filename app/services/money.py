"""Decimal money parsing and rounding shared by all services."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")

# DECIMAL(10,2) in MySQL holds at most 8 digits before the point.
MAX_PRICE = Decimal("99999999.99")


def to_money(value):
    """Round a Decimal to 2 places, half up (2.345 -> 2.35)."""
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def parse_money(text):
    """Parse user input into a 2-place Decimal (never float), or None if invalid."""
    try:
        value = Decimal(str(text).strip())
    except (InvalidOperation, ValueError):
        return None
    if not value.is_finite():
        return None
    return to_money(value)


def parse_whole_number(text):
    """Return an int for input like '12' or '-3', or None for anything else."""
    text = str(text).strip()
    if text == "" or not text.lstrip("-").isdigit():
        return None
    return int(text)
