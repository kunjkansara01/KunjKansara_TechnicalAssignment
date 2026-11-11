"""Admin reports: access, zero-row inclusion, no double counting, filters."""

from decimal import Decimal

from tests.test_order_status import cleanup, create_draft, stock_of  # noqa: F401


def confirm(client, order_id):
    response = client.post("/orders/%d/confirm" % order_id)
    assert response.status_code == 302


def row_text(html, label):
    """Return the <tr> that contains `label`, as text, for simple asserts."""
    html = html.decode()
    start = html.rfind("<tr", 0, html.index(label))
    end = html.index("</tr>", start)
    return html[start:end]


# ---- Access ----

def test_reports_are_admin_only(sales_client, app):
    logged_out = app.test_client()   # separate client with no session at all
    for path in ("/reports/", "/reports/customer-sales", "/reports/product-sales",
                 "/reports/low-stock", "/reports/stock-movements"):
        assert sales_client.get(path).status_code == 403, path
        assert logged_out.get(path).status_code == 302, path   # -> login page


def test_reports_index_links(admin_client):
    body = admin_client.get("/reports/").data
    for path in (b"/reports/customer-sales", b"/reports/product-sales",
                 b"/reports/low-stock", b"/reports/stock-movements"):
        assert path in body


# ---- Customer Sales Summary ----

def test_customer_summary_counts_multi_item_order_once(admin_client, app, cleanup):
    # One order with TWO line items for Patel Electricals (id 3), 10% discount.
    order_id = create_draft(admin_client, [(1, 2), (7, 3)])
    with app.app_context():
        from app.db import get_db
        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE sales_orders SET customer_id = 3, discount_percentage = 10, "
                       "discount_amount = 2545.00, grand_total = 22905.00, "
                       "order_date = '2026-06-10' WHERE id = %s", (order_id,))
        db.commit()
    confirm(admin_client, order_id)

    body = admin_client.get("/reports/customer-sales?date_from=2026-06-01&date_to=2026-06-30").data
    patel = row_text(body, "Patel Electricals")
    # Counted once, with the order's grand_total (not 2x, not the subtotal).
    assert ">1<" in patel
    assert "22,905.00" in patel
    assert "45,810.00" not in patel


def test_customer_summary_includes_customers_with_zero_orders(admin_client):
    body = admin_client.get("/reports/customer-sales?date_from=1999-01-01&date_to=1999-12-31").data
    for name in ("Sunrise Traders", "Green Power Solutions", "Patel Electricals",
                 "Metro Infra Projects", "Old Town Hardware"):
        row = row_text(body, name)
        assert ">0<" in row and "0.00" in row, name


def test_customer_summary_ignores_draft_and_cancelled(admin_client, app, cleanup):
    draft_id = create_draft(admin_client, [(1, 1)])          # stays Draft
    cancelled_id = create_draft(admin_client, [(1, 1)])
    admin_client.post("/orders/%d/cancel" % cancelled_id)
    with app.app_context():
        from app.db import get_db
        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE sales_orders SET customer_id = 4, order_date = '2026-07-01' "
                       "WHERE id IN (%s, %s)", (draft_id, cancelled_id))
        db.commit()

    body = admin_client.get("/reports/customer-sales?date_from=2026-07-01&date_to=2026-07-31").data
    metro = row_text(body, "Metro Infra Projects")
    assert ">0<" in metro


def test_customer_summary_date_filter_and_validation(admin_client, app, cleanup):
    order_id = create_draft(admin_client, [(7, 1)])
    with app.app_context():
        from app.db import get_db
        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE sales_orders SET customer_id = 2, order_date = '2026-08-15' "
                       "WHERE id = %s", (order_id,))
        db.commit()
    confirm(admin_client, order_id)

    inside = admin_client.get("/reports/customer-sales?date_from=2026-08-01&date_to=2026-08-31").data
    assert ">1<" in row_text(inside, "Green Power Solutions")
    outside = admin_client.get("/reports/customer-sales?date_from=2026-09-01&date_to=2026-09-30").data
    assert ">0<" in row_text(outside, "Green Power Solutions")

    bad = admin_client.get("/reports/customer-sales?date_from=15-08-2026").data
    assert b"From date must be in YYYY-MM-DD format." in bad
    reversed_range = admin_client.get("/reports/customer-sales?date_from=2026-09-01&date_to=2026-08-01").data
    assert b"From date must not be after To date." in reversed_range


# ---- Product Sales Summary ----

def test_product_summary_qty_and_gross_value_before_discount(admin_client, app, cleanup):
    # 3 connectors at 150 = 450 gross, order discount 20% should NOT reduce it.
    order_id = create_draft(admin_client, [(7, 3)])
    with app.app_context():
        from app.db import get_db
        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE sales_orders SET discount_percentage = 20, discount_amount = 90.00, "
                       "grand_total = 360.00, order_date = '2026-10-05' WHERE id = %s", (order_id,))
        db.commit()
    confirm(admin_client, order_id)

    body = admin_client.get("/reports/product-sales?date_from=2026-10-01&date_to=2026-10-31").data
    mc4 = row_text(body, "MC4-PAIR")
    assert ">3<" in mc4
    assert "450.00" in mc4
    assert "360.00" not in mc4
    # Unsold product in the range shows zero but is still listed.
    assert ">0<" in row_text(body, "BAT-150")


# ---- Low Stock ----

def test_low_stock_threshold(admin_client, app):
    inverters = stock_of(app, 4)                 # INV-10K, lowest seeded stock
    body = admin_client.get("/reports/low-stock?threshold=%d" % inverters).data
    assert b"INV-10K" in body
    assert b"MC4-PAIR" not in body               # 500 in stock
    assert b"STR-GI" not in body                 # inactive, excluded

    body = admin_client.get("/reports/low-stock?threshold=0").data
    assert b"INV-10K" not in body

    body = admin_client.get("/reports/low-stock?threshold=abc").data
    assert b"Threshold must be a whole number of 0 or more." in body
    assert b'value="10"' in body                 # fell back to the default


# ---- Stock Movement History ----

def test_stock_movement_history_filters(admin_client, app, cleanup):
    order_id = create_draft(admin_client, [(7, 2)])
    confirm(admin_client, order_id)

    body = admin_client.get("/reports/stock-movements?product_id=7&movement_type=order_confirm").data
    assert b"MC4-PAIR" in body
    assert b"-2" in body
    assert b"<td>opening</td>" not in body       # filtered by type (the word stays in the dropdown)

    body = admin_client.get("/reports/stock-movements?movement_type=bogus").data
    assert b"Unknown movement type." in body

    body = admin_client.get("/reports/stock-movements?date_from=2099-01-01").data
    assert b"No stock movements match." in body
