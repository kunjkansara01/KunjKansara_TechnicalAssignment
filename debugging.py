from decimal import Decimal
from app.services import ValidationError, decimal_value, integer, money


def calculate_total(items):
    """Return a Decimal total. Empty input returns 0.00; invalid rows raise ValueError."""
    total = Decimal("0.00")
    for item in items:
        try:
            quantity = integer(item.get("qty"), "Quantity")
            rate = decimal_value(item.get("rate"), "Rate")
        except (ValidationError, AttributeError) as error:
            raise ValueError(str(error)) from error
        total += money(quantity * rate)
    return money(total)
