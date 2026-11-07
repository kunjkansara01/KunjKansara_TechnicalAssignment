# Debugging exercise

The original function assigns `total = amount` on every iteration. This overwrites the previous item, so the supplied example returns 150. The corrected function in `debugging.py` accumulates each amount with `total += amount` and returns 350.00 for the example.

It uses Decimal for money and shares validation with the application. Empty input returns Decimal('0.00'). A missing quantity or rate raises ValueError with a descriptive message. Zero, negative, fractional or boolean quantities are rejected. Negative, nonnumeric and nonfinite rates are rejected. A rate of zero is valid. Rates with more than two decimal places are rejected.

Run `python -m pytest -q tests/test_assignment.py -k debugging` to verify the supplied example, empty input, missing keys and invalid values.
