# Debugging exercise: `calculate_total`

## The bug

The function was meant to add up `qty x rate` for every item in an order.

```python
def calculate_total(items):
    total = 0
    for item in items:
        amount = item['qty'] * item['rate']
        total = amount          # bug
    return total
```

With this input:

```python
[{"qty": 2, "rate": 100}, {"qty": 1, "rate": 150}]
```

the expected total is `2 x 100 + 1 x 150 = 350`, but the function returns
`150`.

## Why it happens

`total = amount` **replaces** the value of `total` on every pass through the
loop. After the first item `total` is 200. After the second item it is
overwritten with 150. Whatever the last item's amount is, that is what comes
back. Every earlier item is silently discarded.

The function only looks correct when the order has exactly one item, which is
why a bug like this can survive a quick manual test.

## The fix

```python
total += amount
```

`+=` means "add to what is already there". After the first item `total` is
200; after the second it is 200 + 150 = 350. This is the one-character
difference between replacing and accumulating.

## Corrected function

The full corrected version lives in [`debugging.py`](../debugging.py) at the
project root so the tests can import it. Besides the fix, it defines the
behaviour the original left to chance:

| Situation | Behaviour |
|-----------|-----------|
| Empty list | Returns `Decimal('0.00')` (equal to `0`) |
| Item missing `qty` or `rate` | Raises `ValueError`, e.g. `Item 2: 'rate' is missing.` |
| `qty` or `rate` is `None` | Raises `ValueError` (treated as missing) |
| `qty` or `rate` not numeric (`"abc"`, `True`) | Raises `ValueError` naming the item and the field |
| `qty` or `rate` negative | Raises `ValueError`, e.g. `Item 1: 'qty' cannot be negative, got -2.` |
| Item is not a dict | Raises `ValueError` |
| `items` is `None` | Raises `ValueError` |
| Numeric strings like `"12.50"` | Accepted and converted |

Valid results are returned as `Decimal` rounded to 2 places with
`ROUND_HALF_UP`, matching the rest of the application's money handling.
`Decimal('350.00') == 350` is `True`, so callers that expect a plain number
still work.

```python
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

def calculate_total(items):
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

        qty = to_decimal(item["qty"], "qty", index)     # validates: numeric, not negative
        rate = to_decimal(item["rate"], "rate", index)

        total += qty * rate                              # accumulate

    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```

`to_decimal` (also in `debugging.py`) does the conversion and raises the
`ValueError` messages for `None`, non-numeric, boolean and negative values.

## Why raise instead of skipping bad items

Skipping an item with a missing rate would return a total that is *smaller
than the real order* without telling anyone. For money, a loud failure is
safer than a quiet wrong answer. The caller sees exactly which item and which
field is wrong and can fix the data.

## How the tests prove it

`tests/test_debugging.py` covers:

- the 350 example (the exact case that exposed the bug),
- a single item (where the buggy version happened to be right),
- three items, so a last-item-only result would be obvious,
- an empty list returning 0,
- a missing `qty`, a missing `rate`, and `None` values,
- non-numeric text and booleans,
- negative `qty` and negative `rate`,
- numeric strings and decimal rounding.

Run them with:

```bash
pytest tests/test_debugging.py -v
```

Or see the fix in action directly:

```bash
python debugging.py
```
