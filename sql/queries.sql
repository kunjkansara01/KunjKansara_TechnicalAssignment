-- =============================================================================
-- Standalone report queries for the Sales Order & Inventory database.
-- Run any of them in the mysql client against sales_inventory.
--
-- A note on the LEFT JOIN pattern used in queries 1 and 3:
--   sales_orders has one row per order, sales_order_items one row per line.
--   Joining customers -> orders -> items and then SUM(grand_total) repeats
--   each order's grand_total once per line item, so a 2-line order counts
--   twice. The fix is to aggregate the orders FIRST in a subquery (one row per
--   customer) and only then join. A LEFT JOIN keeps customers with no rows.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Top 3 customers by total Confirmed grand_total
-- -----------------------------------------------------------------------------
SELECT c.id,
       c.name,
       COALESCE(o.order_count, 0) AS confirmed_orders,
       COALESCE(o.total_sales, 0.00) AS total_sales
FROM customers c
LEFT JOIN (
    SELECT customer_id,
           COUNT(*)         AS order_count,
           SUM(grand_total) AS total_sales
    FROM sales_orders
    WHERE status = 'Confirmed'
    GROUP BY customer_id
) o ON o.customer_id = c.id
ORDER BY total_sales DESC, c.name
LIMIT 3;


-- -----------------------------------------------------------------------------
-- 2. Top 3 products by quantity sold in Confirmed orders
--    Items are the line level, so joining items to their order header is
--    correct here: each line is counted exactly once.
-- -----------------------------------------------------------------------------
SELECT p.id,
       p.product_code,
       p.name,
       SUM(i.quantity) AS qty_sold,
       SUM(i.amount)   AS gross_value
FROM sales_order_items i
JOIN sales_orders o ON o.id = i.sales_order_id
JOIN products     p ON p.id = i.product_id
WHERE o.status = 'Confirmed'
GROUP BY p.id, p.product_code, p.name
ORDER BY qty_sold DESC, p.name
LIMIT 3;


-- -----------------------------------------------------------------------------
-- 3. Customers with no orders at all (any status)
--    LEFT JOIN, then keep only the rows where nothing matched (o.id IS NULL).
-- -----------------------------------------------------------------------------
SELECT c.id, c.name, c.city, c.is_active
FROM customers c
LEFT JOIN sales_orders o ON o.customer_id = c.id
WHERE o.id IS NULL
ORDER BY c.name;


-- -----------------------------------------------------------------------------
-- 4. Month-wise Confirmed totals, grouped by year and month
-- -----------------------------------------------------------------------------
SELECT YEAR(order_date)  AS order_year,
       MONTH(order_date) AS order_month,
       COUNT(*)          AS confirmed_orders,
       SUM(subtotal)     AS subtotal,
       SUM(discount_amount) AS discount,
       SUM(grand_total)  AS grand_total
FROM sales_orders
WHERE status = 'Confirmed'
GROUP BY YEAR(order_date), MONTH(order_date)
ORDER BY order_year, order_month;


-- -----------------------------------------------------------------------------
-- 5. Active products at or below a stock threshold
--    Change @threshold to the level you care about.
-- -----------------------------------------------------------------------------
SET @threshold = 10;

SELECT id, product_code, name, category, stock_quantity
FROM products
WHERE is_active = TRUE
  AND stock_quantity <= @threshold
ORDER BY stock_quantity, name;
