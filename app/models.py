"""One function per SQL query. Never commits: the calling service owns the transaction."""

from app.db import get_db


# ---- users ----

def get_user_by_email(email):
    """Return the user row for this email (including password_hash), or None."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, name, email, password_hash, role FROM users WHERE email = %s",
        (email,),
    )
    user = cursor.fetchone()
    cursor.close()
    return user


# ---- customers ----

def list_customers(search="", status="active"):
    """Customers filtered by search text (name/email/mobile) and status (active/inactive/all)."""
    sql = "SELECT id, name, email, mobile, city, is_active FROM customers WHERE 1 = 1"
    params = []

    if search:
        like = "%" + search + "%"
        sql += " AND (name LIKE %s OR email LIKE %s OR mobile LIKE %s)"
        params.extend([like, like, like])

    if status == "active":
        sql += " AND is_active = TRUE"
    elif status == "inactive":
        sql += " AND is_active = FALSE"

    sql += " ORDER BY name"

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    cursor.close()
    return rows


def get_customer_by_id(customer_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, name, email, mobile, city, is_active FROM customers WHERE id = %s",
        (customer_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    return row


def insert_customer(name, email, mobile, city):
    """Insert a new active customer and return its new id."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO customers (name, email, mobile, city, is_active) "
        "VALUES (%s, %s, %s, %s, TRUE)",
        (name, email, mobile, city),
    )
    new_id = cursor.lastrowid
    cursor.close()
    return new_id


def update_customer(customer_id, name, email, mobile, city):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE customers SET name = %s, email = %s, mobile = %s, city = %s WHERE id = %s",
        (name, email, mobile, city, customer_id),
    )
    cursor.close()


def set_customer_active(customer_id, is_active):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE customers SET is_active = %s WHERE id = %s",
        (is_active, customer_id),
    )
    cursor.close()


def count_orders_for_customer(customer_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM sales_orders WHERE customer_id = %s",
        (customer_id,),
    )
    count = cursor.fetchone()[0]
    cursor.close()
    return count


def delete_customer(customer_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM customers WHERE id = %s", (customer_id,))
    cursor.close()


# ---- products ----

PRODUCT_COLUMNS = "id, product_code, name, category, price, stock_quantity, is_active"


def product_filter_sql(search, category, status):
    """WHERE clause shared by list_products and count_products so they can never disagree."""
    sql = " WHERE 1 = 1"
    params = []

    if search:
        like = "%" + search + "%"
        sql += " AND (product_code LIKE %s OR name LIKE %s)"
        params.extend([like, like])

    if category:
        sql += " AND category = %s"
        params.append(category)

    if status == "active":
        sql += " AND is_active = TRUE"
    elif status == "inactive":
        sql += " AND is_active = FALSE"

    return sql, params


def list_products(search="", category="", status="active", limit=None, offset=0):
    """Products filtered by search (code/name), category and status, with optional paging."""
    where_sql, params = product_filter_sql(search, category, status)
    sql = "SELECT " + PRODUCT_COLUMNS + " FROM products" + where_sql + " ORDER BY name"

    if limit is not None:
        sql += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    cursor.close()
    return rows


def count_products(search="", category="", status="active"):
    """How many products match the same filters as list_products."""
    where_sql, params = product_filter_sql(search, category, status)
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM products" + where_sql, params)
    count = cursor.fetchone()[0]
    cursor.close()
    return count


def list_product_categories():
    """Return the distinct category names in use, for the filter dropdown."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT DISTINCT category FROM products "
        "WHERE category IS NOT NULL AND category <> '' ORDER BY category"
    )
    categories = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return categories


def get_product_by_id(product_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT " + PRODUCT_COLUMNS + " FROM products WHERE id = %s",
        (product_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    return row


def get_product_by_id_for_update(product_id):
    """FOR UPDATE: lock the row so two requests cannot both act on the same stock figure."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT " + PRODUCT_COLUMNS + " FROM products WHERE id = %s FOR UPDATE",
        (product_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    return row


def get_product_by_code(product_code):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT " + PRODUCT_COLUMNS + " FROM products WHERE product_code = %s",
        (product_code,),
    )
    row = cursor.fetchone()
    cursor.close()
    return row


def insert_product(product_code, name, category, price, stock_quantity):
    """Insert a new active product and return its new id."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO products (product_code, name, category, price, stock_quantity, is_active) "
        "VALUES (%s, %s, %s, %s, %s, TRUE)",
        (product_code, name, category, price, stock_quantity),
    )
    new_id = cursor.lastrowid
    cursor.close()
    return new_id


def update_product(product_id, product_code, name, category, price):
    """Update the editable fields. Stock is changed only through movements."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE products SET product_code = %s, name = %s, category = %s, price = %s "
        "WHERE id = %s",
        (product_code, name, category, price, product_id),
    )
    cursor.close()


def update_product_stock(product_id, new_stock_quantity):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE products SET stock_quantity = %s WHERE id = %s",
        (new_stock_quantity, product_id),
    )
    cursor.close()


def set_product_active(product_id, is_active):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE products SET is_active = %s WHERE id = %s",
        (is_active, product_id),
    )
    cursor.close()


def count_order_items_for_product(product_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM sales_order_items WHERE product_id = %s",
        (product_id,),
    )
    count = cursor.fetchone()[0]
    cursor.close()
    return count


def count_stock_movements_for_product(product_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM stock_movements WHERE product_id = %s",
        (product_id,),
    )
    count = cursor.fetchone()[0]
    cursor.close()
    return count


def delete_product(product_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
    cursor.close()


# ---- stock movements ----

def insert_stock_movement(product_id, movement_type, quantity_change, sales_order_id, reason, created_by):
    """Record one change to a product's stock. Returns the new id."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO stock_movements "
        "(product_id, movement_type, quantity_change, sales_order_id, reason, created_by) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (product_id, movement_type, quantity_change, sales_order_id, reason, created_by),
    )
    new_id = cursor.lastrowid
    cursor.close()
    return new_id


def list_stock_movements_for_product(product_id):
    """Newest first, with the name of the user who made each change."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT m.id, m.movement_type, m.quantity_change, m.sales_order_id, m.reason, "
        "       m.created_at, u.name AS created_by_name "
        "FROM stock_movements m "
        "JOIN users u ON u.id = m.created_by "
        "WHERE m.product_id = %s "
        "ORDER BY m.created_at DESC, m.id DESC",
        (product_id,),
    )
    rows = cursor.fetchall()
    cursor.close()
    return rows


# ---- sales orders ----
# Ownership is enforced in the SQL: a sales user only ever matches their own orders.

def list_orders(user, search="", status=""):
    sql = (
        "SELECT o.id, o.order_number, o.order_date, o.status, o.grand_total, "
        "       c.name AS customer_name, u.name AS created_by_name "
        "FROM sales_orders o "
        "JOIN customers c ON c.id = o.customer_id "
        "JOIN users u ON u.id = o.created_by "
        "WHERE 1 = 1"
    )
    params = []

    if user["role"] != "admin":
        sql += " AND o.created_by = %s"
        params.append(user["id"])

    if search:
        like = "%" + search + "%"
        sql += " AND (o.order_number LIKE %s OR c.name LIKE %s)"
        params.extend([like, like])

    if status:
        sql += " AND o.status = %s"
        params.append(status)

    sql += " ORDER BY o.order_date DESC, o.id DESC"

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    cursor.close()
    return rows


def get_order(order_id, user):
    """Return one order header the user is allowed to see, or None."""
    sql = (
        "SELECT o.id, o.order_number, o.customer_id, o.order_date, o.status, "
        "       o.discount_percentage, o.subtotal, o.discount_amount, o.grand_total, "
        "       o.created_by, o.created_at, o.updated_at, "
        "       c.name AS customer_name, u.name AS created_by_name "
        "FROM sales_orders o "
        "JOIN customers c ON c.id = o.customer_id "
        "JOIN users u ON u.id = o.created_by "
        "WHERE o.id = %s"
    )
    params = [order_id]

    if user["role"] != "admin":
        sql += " AND o.created_by = %s"
        params.append(user["id"])

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(sql, params)
    row = cursor.fetchone()
    cursor.close()
    return row


def order_exists(order_id):
    """True if the id exists for anyone: lets routes answer 403 (not yours) instead of 404."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT 1 FROM sales_orders WHERE id = %s", (order_id,))
    found = cursor.fetchone() is not None
    cursor.close()
    return found


def list_order_items(order_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT i.id, i.product_id, i.quantity, i.rate, i.amount, "
        "       p.product_code, p.name AS product_name "
        "FROM sales_order_items i "
        "JOIN products p ON p.id = i.product_id "
        "WHERE i.sales_order_id = %s "
        "ORDER BY i.id",
        (order_id,),
    )
    rows = cursor.fetchall()
    cursor.close()
    return rows


def get_max_order_sequence_for_year(year):
    """Highest NNNN used in 'SO-<year>-NNNN'. Cast to int because as text '9999' > '10000'."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT MAX(CAST(SUBSTRING_INDEX(order_number, '-', -1) AS UNSIGNED)) "
        "FROM sales_orders WHERE order_number LIKE %s",
        ("SO-%d-%%" % year,),
    )
    value = cursor.fetchone()[0]
    cursor.close()
    return value


def insert_order(order_number, customer_id, order_date, discount_percentage,
                 subtotal, discount_amount, grand_total, created_by):
    """Insert a Draft order header and return its new id."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO sales_orders "
        "(order_number, customer_id, order_date, status, discount_percentage, "
        " subtotal, discount_amount, grand_total, created_by) "
        "VALUES (%s, %s, %s, 'Draft', %s, %s, %s, %s, %s)",
        (order_number, customer_id, order_date, discount_percentage,
         subtotal, discount_amount, grand_total, created_by),
    )
    new_id = cursor.lastrowid
    cursor.close()
    return new_id


def update_order_header(order_id, customer_id, order_date, discount_percentage,
                        subtotal, discount_amount, grand_total):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE sales_orders SET customer_id = %s, order_date = %s, discount_percentage = %s, "
        "subtotal = %s, discount_amount = %s, grand_total = %s "
        "WHERE id = %s",
        (customer_id, order_date, discount_percentage,
         subtotal, discount_amount, grand_total, order_id),
    )
    cursor.close()


def insert_order_item(order_id, product_id, quantity, rate, amount):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO sales_order_items (sales_order_id, product_id, quantity, rate, amount) "
        "VALUES (%s, %s, %s, %s, %s)",
        (order_id, product_id, quantity, rate, amount),
    )
    cursor.close()


def delete_order_items(order_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM sales_order_items WHERE sales_order_id = %s", (order_id,))
    cursor.close()


# ---- sales orders: locking reads for confirm / cancel ----

def get_order_for_update(order_id):
    """FOR UPDATE on the order row: a repeated confirm/cancel waits, then sees the new status."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, order_number, status, created_by FROM sales_orders "
        "WHERE id = %s FOR UPDATE",
        (order_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    return row


def list_order_items_with_products_for_update(order_id):
    """FOR UPDATE on the order's product rows, in product_id order: no overselling, no deadlocks."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT i.product_id, i.quantity, p.product_code, p.name AS product_name, "
        "       p.stock_quantity "
        "FROM sales_order_items i "
        "JOIN products p ON p.id = i.product_id "
        "WHERE i.sales_order_id = %s "
        "ORDER BY i.product_id "
        "FOR UPDATE",
        (order_id,),
    )
    rows = cursor.fetchall()
    cursor.close()
    return rows


def update_order_status(order_id, status):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE sales_orders SET status = %s WHERE id = %s",
        (status, order_id),
    )
    cursor.close()


# ---- reports (admin only) ----
# Aggregate in a subquery, then LEFT JOIN: no double-counting of multi-item orders, zero rows kept.

def date_range_sql(column, date_from, date_to):
    """Return (sql_fragment, params) limiting `column` to an optional range."""
    sql = ""
    params = []
    if date_from is not None:
        sql += " AND " + column + " >= %s"
        params.append(date_from)
    if date_to is not None:
        sql += " AND " + column + " <= %s"
        params.append(date_to)
    return sql, params


def report_customer_sales(date_from=None, date_to=None):
    """Confirmed order count and total per customer; customers with none appear with zeros."""
    range_sql, params = date_range_sql("order_date", date_from, date_to)
    sql = (
        "SELECT c.id, c.name, c.city, c.is_active, "
        "       COALESCE(o.order_count, 0) AS order_count, "
        "       COALESCE(o.total_sales, 0.00) AS total_sales "
        "FROM customers c "
        "LEFT JOIN ( "
        "    SELECT customer_id, COUNT(*) AS order_count, SUM(grand_total) AS total_sales "
        "    FROM sales_orders "
        "    WHERE status = 'Confirmed'" + range_sql + " "
        "    GROUP BY customer_id "
        ") o ON o.customer_id = c.id "
        "ORDER BY total_sales DESC, c.name"
    )
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    cursor.close()
    return rows


def report_product_sales(date_from=None, date_to=None):
    """Qty sold and gross item value (before order discount) per product, Confirmed orders only."""
    range_sql, params = date_range_sql("o.order_date", date_from, date_to)
    sql = (
        "SELECT p.id, p.product_code, p.name, p.category, p.stock_quantity, p.is_active, "
        "       COALESCE(s.qty_sold, 0) AS qty_sold, "
        "       COALESCE(s.gross_value, 0.00) AS gross_value "
        "FROM products p "
        "LEFT JOIN ( "
        "    SELECT i.product_id, SUM(i.quantity) AS qty_sold, SUM(i.amount) AS gross_value "
        "    FROM sales_order_items i "
        "    JOIN sales_orders o ON o.id = i.sales_order_id "
        "    WHERE o.status = 'Confirmed'" + range_sql + " "
        "    GROUP BY i.product_id "
        ") s ON s.product_id = p.id "
        "ORDER BY qty_sold DESC, p.name"
    )
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    cursor.close()
    return rows


def report_low_stock(threshold):
    """Active products whose stock is at or below the threshold."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, product_code, name, category, price, stock_quantity "
        "FROM products "
        "WHERE is_active = TRUE AND stock_quantity <= %s "
        "ORDER BY stock_quantity, name",
        (threshold,),
    )
    rows = cursor.fetchall()
    cursor.close()
    return rows


def report_stock_movements(product_id=None, movement_type=None,
                           date_from=None, date_to=None, limit=500):
    """Stock movement history, newest first, with optional filters."""
    sql = (
        "SELECT m.id, m.created_at, m.movement_type, m.quantity_change, m.reason, "
        "       p.product_code, p.name AS product_name, "
        "       o.order_number, u.name AS created_by_name "
        "FROM stock_movements m "
        "JOIN products p ON p.id = m.product_id "
        "LEFT JOIN sales_orders o ON o.id = m.sales_order_id "
        "JOIN users u ON u.id = m.created_by "
        "WHERE 1 = 1"
    )
    params = []

    if product_id is not None:
        sql += " AND m.product_id = %s"
        params.append(product_id)
    if movement_type:
        sql += " AND m.movement_type = %s"
        params.append(movement_type)

    # Compare on DATE(created_at) so the "to" date includes that whole day.
    range_sql, range_params = date_range_sql("DATE(m.created_at)", date_from, date_to)
    sql += range_sql
    params.extend(range_params)

    sql += " ORDER BY m.created_at DESC, m.id DESC LIMIT %s"
    params.append(limit)

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    cursor.close()
    return rows
