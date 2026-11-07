-- 1. Top three customers by confirmed sales after discount.
SELECT c.id, c.name, SUM(o.grand_total) AS total_sales
FROM customers c JOIN sales_orders o ON o.customer_id = c.id
WHERE o.status = 'Confirmed'
GROUP BY c.id, c.name ORDER BY total_sales DESC, c.id LIMIT 3;

-- 2. Top three products by confirmed quantity sold.
SELECT p.id, p.product_code, p.name, SUM(i.quantity) AS quantity_sold
FROM products p JOIN sales_order_items i ON i.product_id = p.id
JOIN sales_orders o ON o.id = i.order_id
WHERE o.status = 'Confirmed'
GROUP BY p.id, p.product_code, p.name ORDER BY quantity_sold DESC, p.id LIMIT 3;

-- 3. Customers who have never placed any order, including drafts or cancellations.
SELECT c.id, c.name FROM customers c
WHERE NOT EXISTS (SELECT 1 FROM sales_orders o WHERE o.customer_id = c.id);

-- 4. Month-wise confirmed sales, preserving the year boundary.
SELECT YEAR(order_date) AS sales_year, MONTH(order_date) AS sales_month,
       SUM(grand_total) AS total_sales
FROM sales_orders WHERE status = 'Confirmed'
GROUP BY YEAR(order_date), MONTH(order_date) ORDER BY sales_year, sales_month;

-- 5. Supply the threshold as a bound parameter in the application.
SET @stock_threshold = 10;
SELECT product_code, name, stock_quantity FROM products
WHERE stock_quantity < @stock_threshold ORDER BY stock_quantity, product_code;
