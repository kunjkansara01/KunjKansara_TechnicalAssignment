"""Debugging exercise: calculate_total.

THE ORIGINAL (BUGGY) CODE
-------------------------
    def calculate_total(items):
        total = 0
        for item in items:
            amount = item['qty'] * item['rate']
            total = amount          # <-- BUG: overwrites instead of adding
        return total

For items [{qty: 2, rate: 100}, {qty: 1, rate: 150}] it returns 150, the
amount of the LAST item, instead of 350. Each loop pass replaces `total`
with the current line's amount, so every earlier line is thrown away.

THE FIX
-------
    total += amount

`+=` adds the current amount to the running total, so the total accumulates
across every item. The corrected function below also defines behaviour for
the cases the original left undefined: an empty list, missing keys, and
values that are not valid non-negative numbers.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

TWO_PLACES = Decimal("0.01")


def to_decimal(value, field_name, item_number):
    """Convert a qty or rate to Decimal, or raise ValueError with a clear message.

    Accepts int, float, Decimal, or a numeric string like "12.50".
    Rejects None, text that is not a number, and negative numbers.
    """
    if value is None:
        raise ValueError("Item %d: '%s' is missing." % (item_number, field_name))

    # bool is a subclass of int in Python; True * 100 would silently be 100.
    if isinstance(value, bool):
        raise ValueError("Item %d: '%s' must be a number, got %r." % (item_number, field_name, value))

    try:
        # str() first so a float like 0.1 is read as "0.1", not its binary
        # approximation 0.1000000000000000055511151231257827...
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Item %d: '%s' must be a number, got %r." % (item_number, field_name, value))

    if not number.is_finite():
        raise ValueError("Item %d: '%s' must be a number, got %r." % (item_number, field_name, value))

    if number < 0:
        raise ValueError("Item %d: '%s' cannot be negative, got %s." % (item_number, field_name, number))

    return number


def calculate_total(items):
    """Return the sum of qty x rate over all items, as a Decimal with 2 places.

    items: a list of dicts, each with 'qty' and 'rate'.

    Defined behaviour
      * empty list                -> Decimal('0.00')
      * missing 'qty' or 'rate'   -> ValueError naming the item and the key
      * non-numeric qty or rate   -> ValueError
      * negative qty or rate      -> ValueError
    """
    if items is None:
        raise ValueError("items must be a list, got None.")

    total = Decimal("0.00")

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError("Item %d must be a dict with 'qty' and 'rate', got %r." % (index, item))

        if "qty" not in item:
            raise ValueError("Item %d: 'qty' is missing." % index)
        if "rate" not in item:
            raise ValueError("Item %d: 'rate' is missing." % index)

        qty = to_decimal(item["qty"], "qty", index)
        rate = to_decimal(item["rate"], "rate", index)

        amount = qty * rate
        total += amount          # accumulate (the original did total = amount)

    return total.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


if __name__ == "__main__":
    # Quick demonstration: python debugging.py
    sample = [{"qty": 2, "rate": 100}, {"qty": 1, "rate": 150}]
    print("Items:", sample)
    print("Total:", calculate_total(sample))   # 350.00
