"""CSV product import: validate every row, then import all or nothing in one transaction."""

import csv
import io

import mysql.connector

from app import models
from app.db import get_db
from app.services.money import MAX_PRICE, parse_money, parse_whole_number

EXPECTED_HEADER = ["product_code", "product_name", "category", "price", "stock_quantity", "status"]
STATUS_VALUES = {"active": True, "inactive": False}
MAX_ROWS = 5000


def decode_upload(raw_bytes):
    try:
        # utf-8-sig: Excel CSVs start with a BOM (\ufeff) that would break the header check.
        return raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None


def parse_csv(text):
    reader = csv.reader(io.StringIO(text))
    header = None
    data_rows = []
    for row_number, cells in enumerate(reader, start=1):
        if all(cell.strip() == "" for cell in cells):
            continue
        if header is None:
            header = [cell.strip().lower() for cell in cells]
        else:
            data_rows.append((row_number, cells))
    return header, data_rows


def validate_rows(header, data_rows):
    errors = []

    if header is None:
        return [], [{"row": 1, "message": "The file is empty."}]

    if header != EXPECTED_HEADER:
        return [], [{
            "row": 1,
            "message": "Header must be exactly: %s (got: %s)."
                       % (",".join(EXPECTED_HEADER), ",".join(header)),
        }]

    if not data_rows:
        return [], [{"row": 2, "message": "The file has a header but no product rows."}]

    if len(data_rows) > MAX_ROWS:
        return [], [{"row": 1, "message": "Too many rows (limit %d per file)." % MAX_ROWS}]

    clean_products = []
    codes_seen_in_file = {}

    for row_number, cells in data_rows:
        if len(cells) != len(EXPECTED_HEADER):
            errors.append({
                "row": row_number,
                "message": "Expected %d columns but found %d." % (len(EXPECTED_HEADER), len(cells)),
            })
            continue

        code, name, category, price_text, stock_text, status_text = [cell.strip() for cell in cells]
        code = code.upper()

        # --- product_code -----------------------------------------------------
        if code == "":
            errors.append({"row": row_number, "message": "product_code is required."})
        elif len(code) > 50:
            errors.append({"row": row_number, "message": "product_code must be 50 characters or fewer."})
        else:
            if code in codes_seen_in_file:
                errors.append({
                    "row": row_number,
                    "message": "product_code '%s' is duplicated in this file (first seen on row %d)."
                               % (code, codes_seen_in_file[code]),
                })
            else:
                codes_seen_in_file[code] = row_number
                if models.get_product_by_code(code) is not None:
                    errors.append({
                        "row": row_number,
                        "message": "product_code '%s' already exists in the database." % code,
                    })

        # --- product_name / category ------------------------------------------
        if name == "":
            errors.append({"row": row_number, "message": "product_name is required."})
        elif len(name) > 150:
            errors.append({"row": row_number, "message": "product_name must be 150 characters or fewer."})

        if len(category) > 100:
            errors.append({"row": row_number, "message": "category must be 100 characters or fewer."})

        # --- price ------------------------------------------------------------
        price = parse_money(price_text)
        if price is None:
            errors.append({"row": row_number, "message": "price '%s' is not a number." % price_text})
        elif price < 0:
            errors.append({"row": row_number, "message": "price cannot be negative."})
        elif price > MAX_PRICE:
            errors.append({"row": row_number, "message": "price is too large."})

        # --- stock_quantity ---------------------------------------------------
        stock = parse_whole_number(stock_text)
        if stock is None:
            errors.append({"row": row_number, "message": "stock_quantity '%s' is not a whole number." % stock_text})
        elif stock < 0:
            errors.append({"row": row_number, "message": "stock_quantity cannot be negative."})

        # --- status -----------------------------------------------------------
        is_active = STATUS_VALUES.get(status_text.lower())
        if is_active is None:
            errors.append({"row": row_number, "message": "status '%s' must be Active or Inactive." % status_text})

        clean_products.append({
            "row": row_number,
            "product_code": code,
            "name": name,
            "category": category if category != "" else None,
            "price": price,
            "stock_quantity": stock,
            "is_active": is_active,
        })

    return clean_products, errors


def import_products(clean_products, user_id):
    db = get_db()
    try:
        for product in clean_products:
            product_id = models.insert_product(
                product["product_code"], product["name"], product["category"],
                product["price"], product["stock_quantity"],
            )
            if not product["is_active"]:
                models.set_product_active(product_id, False)
            if product["stock_quantity"] > 0:
                models.insert_stock_movement(
                    product_id, "opening", product["stock_quantity"],
                    None, "Opening stock (CSV import)", user_id,
                )
        db.commit()
    except mysql.connector.Error:
        db.rollback()
        raise
    return len(clean_products)


def process_upload(raw_bytes, user_id):
    text = decode_upload(raw_bytes)
    if text is None:
        return 0, [{"row": 1, "message": "The file is not valid UTF-8 text. Save it as CSV (UTF-8)."}]

    header, data_rows = parse_csv(text)
    clean_products, errors = validate_rows(header, data_rows)
    if errors:
        return 0, errors

    return import_products(clean_products, user_id), []
