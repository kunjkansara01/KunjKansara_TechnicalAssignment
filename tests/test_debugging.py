"""Unit tests for the corrected calculate_total (no database, no Flask)."""

from decimal import Decimal

import pytest

from debugging import calculate_total


# ---- The fix: totals accumulate across items ----

def test_the_350_example():
    items = [{"qty": 2, "rate": 100}, {"qty": 1, "rate": 150}]
    assert calculate_total(items) == 350
    # The buggy version returned only the last amount:
    assert calculate_total(items) != 150


def test_single_item_still_correct():
    # The only case where the buggy code gave the right answer.
    assert calculate_total([{"qty": 3, "rate": 50}]) == 150


def test_three_items_accumulate():
    items = [{"qty": 1, "rate": 10}, {"qty": 2, "rate": 20}, {"qty": 3, "rate": 30}]
    assert calculate_total(items) == 10 + 40 + 90      # 140, not 90


def test_zero_quantity_contributes_nothing():
    items = [{"qty": 0, "rate": 999}, {"qty": 2, "rate": 5}]
    assert calculate_total(items) == 10


# ---- Empty list ----

def test_empty_list_returns_zero():
    result = calculate_total([])
    assert result == 0
    assert result == Decimal("0.00")
    assert isinstance(result, Decimal)


# ---- Missing qty / rate ----

def test_missing_qty_raises_with_item_number():
    with pytest.raises(ValueError, match="Item 2: 'qty' is missing."):
        calculate_total([{"qty": 1, "rate": 10}, {"rate": 10}])


def test_missing_rate_raises_with_item_number():
    with pytest.raises(ValueError, match="Item 1: 'rate' is missing."):
        calculate_total([{"qty": 1}])


def test_none_values_are_treated_as_missing():
    with pytest.raises(ValueError, match="Item 1: 'rate' is missing."):
        calculate_total([{"qty": 1, "rate": None}])
    with pytest.raises(ValueError, match="Item 1: 'qty' is missing."):
        calculate_total([{"qty": None, "rate": 1}])


def test_item_that_is_not_a_dict_raises():
    with pytest.raises(ValueError, match="Item 1 must be a dict"):
        calculate_total([("qty", 1)])


def test_none_instead_of_list_raises():
    with pytest.raises(ValueError, match="items must be a list"):
        calculate_total(None)


# ---- Invalid values ----

def test_non_numeric_qty_rejected():
    with pytest.raises(ValueError, match="Item 1: 'qty' must be a number, got 'two'"):
        calculate_total([{"qty": "two", "rate": 10}])


def test_non_numeric_rate_rejected():
    with pytest.raises(ValueError, match="Item 1: 'rate' must be a number, got 'abc'"):
        calculate_total([{"qty": 1, "rate": "abc"}])


def test_boolean_is_not_a_number():
    # True would otherwise behave like 1 and hide a data error.
    with pytest.raises(ValueError, match="'qty' must be a number, got True"):
        calculate_total([{"qty": True, "rate": 10}])


def test_negative_qty_rejected():
    with pytest.raises(ValueError, match="Item 1: 'qty' cannot be negative, got -2"):
        calculate_total([{"qty": -2, "rate": 10}])


def test_negative_rate_rejected():
    with pytest.raises(ValueError, match="Item 2: 'rate' cannot be negative, got -5"):
        calculate_total([{"qty": 1, "rate": 10}, {"qty": 1, "rate": -5}])


def test_error_in_later_item_means_no_partial_total():
    # The function raises; it never returns a total that silently skips item 2.
    with pytest.raises(ValueError):
        calculate_total([{"qty": 1, "rate": 10}, {"qty": 1, "rate": "bad"}])


# ---- Accepted formats and rounding ----

def test_numeric_strings_are_accepted():
    assert calculate_total([{"qty": "2", "rate": "12.50"}]) == Decimal("25.00")


def test_decimal_inputs_and_rounding_half_up():
    # 3 x 0.335 = 1.005 -> 1.01 with ROUND_HALF_UP (not 1.00)
    assert calculate_total([{"qty": 3, "rate": Decimal("0.335")}]) == Decimal("1.01")


def test_float_inputs_do_not_drift():
    # 0.1 + 0.2 in binary floats is 0.30000000000000004; here it is exactly 0.30
    assert calculate_total([{"qty": 1, "rate": 0.1}, {"qty": 1, "rate": 0.2}]) == Decimal("0.30")
