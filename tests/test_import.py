"""CSV product import: validation, all-or-nothing, opening movements."""

import io
import os
from decimal import Decimal

import pytest

from app.db import get_db

SAMPLES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "samples")
VALID_CODES = ["SP-600", "INV-3K", "BAT-200", "CBL-6MM", "STR-AL"]
HEADER = "product_code,product_name,category,price,stock_quantity,status\n"


@pytest.fixture
def cleanup(app):
    yield
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        codes = VALID_CODES + ["NEW-%03d" % n for n in range(1, 10)] + ["T-1", "T-2"]
        placeholders = ",".join(["%s"] * len(codes))
        cursor.execute(
            "DELETE FROM stock_movements WHERE product_id IN "
            "(SELECT id FROM products WHERE product_code IN (%s))" % placeholders, codes)
        cursor.execute("DELETE FROM products WHERE product_code IN (%s)" % placeholders, codes)
        db.commit()
        cursor.close()


def upload(client, content, filename="products.csv"):
    if isinstance(content, str):
        content = content.encode("utf-8")
    return client.post(
        "/products/import",
        data={"file": (io.BytesIO(content), filename)},
        content_type="multipart/form-data",
        follow_redirects=True,
    )


def fetch_products(app, codes):
    with app.app_context():
        cursor = get_db().cursor(dictionary=True)
        cursor.execute(
            "SELECT p.product_code, p.price, p.stock_quantity, p.is_active, "
            "       (SELECT COUNT(*) FROM stock_movements m WHERE m.product_id = p.id) AS movements "
            "FROM products p WHERE p.product_code IN (%s) ORDER BY p.product_code"
            % ",".join(["%s"] * len(codes)), codes)
        rows = cursor.fetchall()
        cursor.close()
        return {row["product_code"]: row for row in rows}


# ---- Access ----

def test_import_is_admin_only(sales_client):
    assert sales_client.get("/products/import").status_code == 403
    assert upload(sales_client, HEADER + "T-1,x,c,1,1,Active\n").status_code == 403


def test_import_page_loads(admin_client):
    response = admin_client.get("/products/import")
    assert response.status_code == 200
    assert b"product_code,product_name,category,price,stock_quantity,status" in response.data


# ---- Valid sample ----

def test_valid_sample_imports_everything(admin_client, app, cleanup):
    with open(os.path.join(SAMPLES, "valid_products.csv"), "rb") as f:
        response = upload(admin_client, f.read(), "valid_products.csv")

    assert response.status_code == 200
    assert b"5 product(s) imported from valid_products.csv." in response.data

    rows = fetch_products(app, VALID_CODES)
    assert sorted(rows) == sorted(VALID_CODES)

    assert rows["SP-600"]["price"] == Decimal("14250.00")
    assert rows["SP-600"]["stock_quantity"] == 40
    assert rows["SP-600"]["movements"] == 1          # opening movement written
    assert rows["BAT-200"]["price"] == Decimal("82000.50")
    assert rows["BAT-200"]["stock_quantity"] == 0
    assert rows["BAT-200"]["movements"] == 0         # zero stock -> no movement
    assert rows["STR-AL"]["is_active"] == 0
    assert rows["STR-AL"]["price"] == Decimal("5200.75")

    with app.app_context():
        cursor = get_db().cursor()
        cursor.execute(
            "SELECT m.movement_type, m.quantity_change, m.reason FROM stock_movements m "
            "JOIN products p ON p.id = m.product_id WHERE p.product_code = 'INV-3K'")
        assert cursor.fetchone() == ("opening", 12, "Opening stock (CSV import)")


# ---- Invalid sample: every error reported, nothing imported ----

def test_invalid_sample_reports_all_errors_and_imports_nothing(admin_client, app, cleanup):
    with open(os.path.join(SAMPLES, "invalid_products.csv"), "rb") as f:
        response = upload(admin_client, f.read(), "invalid_products.csv")

    assert response.status_code == 400
    body = response.data.decode()
    assert "Import rejected: invalid_products.csv" in body
    assert "No products were saved." in body

    expected = [
        (2, "product_code &#39;SP-540&#39; already exists in the database."),
        (3, "product_code is required."),
        (4, "price &#39;abc&#39; is not a number."),
        (5, "stock_quantity cannot be negative."),
        (6, "status &#39;Pending&#39; must be Active or Inactive."),
        (8, "product_code &#39;NEW-004&#39; is duplicated in this file (first seen on row 7)."),
        (9, "Expected 6 columns but found 4."),
        (10, "price cannot be negative."),
    ]
    for row, message in expected:
        assert message in body, message
        assert ("<td class=\"num\">%d</td>" % row) in body, row

    # Row 7 (first NEW-004) was fine and must NOT be reported.
    assert '<td class="num">7</td>' not in body

    # Absolutely nothing was written, including the valid rows.
    assert fetch_products(app, ["NEW-%03d" % n for n in range(1, 7)]) == {}


# ---- Header and file-level problems ----

def test_wrong_header_rejected(admin_client, cleanup):
    response = upload(admin_client, "code,name,price\nT-1,x,1\n")
    assert response.status_code == 400
    assert b"Header must be exactly: product_code,product_name,category,price,stock_quantity,status" in response.data


def test_header_is_case_and_space_insensitive(admin_client, app, cleanup):
    response = upload(admin_client,
                      "Product_Code, Product_Name ,CATEGORY,Price,Stock_Quantity,Status\n"
                      "T-1,Test one,Cat,10,1,active\n")
    assert b"1 product(s) imported" in response.data
    assert fetch_products(app, ["T-1"])["T-1"]["is_active"] == 1


def test_empty_file_and_header_only(admin_client, cleanup):
    assert b"The file is empty." in upload(admin_client, "").data
    assert b"The file has a header but no product rows." in upload(admin_client, HEADER).data
    assert b"The file has a header but no product rows." in upload(admin_client, HEADER + "\n\n").data


def test_no_file_chosen(admin_client):
    response = admin_client.post("/products/import", data={}, content_type="multipart/form-data")
    assert response.status_code == 400
    assert b"Choose a CSV file to upload." in response.data


def test_non_utf8_file_rejected(admin_client, cleanup):
    response = upload(admin_client, b"\xff\xfe\x00bad bytes")
    assert response.status_code == 400
    assert b"not valid UTF-8 text" in response.data


def test_bom_from_excel_is_tolerated(admin_client, app, cleanup):
    content = b"\xef\xbb\xbf" + (HEADER + "T-2,With BOM,Cat,5,2,Active\n").encode("utf-8")
    response = upload(admin_client, content)
    assert b"1 product(s) imported" in response.data
    assert "T-2" in fetch_products(app, ["T-2"])


def test_one_bad_row_blocks_good_rows(admin_client, app, cleanup):
    response = upload(admin_client, HEADER +
                      "T-1,Good row,Cat,10,1,Active\n"
                      "T-2,Bad row,Cat,ten,1,Active\n")
    assert response.status_code == 400
    assert b"price &#39;ten&#39; is not a number." in response.data
    assert fetch_products(app, ["T-1", "T-2"]) == {}
