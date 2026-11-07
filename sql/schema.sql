-- MySQL 8.4 schema. Run inside the sales_inventory database.

CREATE TABLE customers (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(120) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	mobile VARCHAR(30) NOT NULL, 
	city VARCHAR(100) NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (status IN ('Active', 'Inactive'))
) ENGINE=InnoDB;

CREATE TABLE products (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	product_code VARCHAR(50) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	category VARCHAR(100) NOT NULL, 
	price NUMERIC(14, 2) NOT NULL, 
	stock_quantity INTEGER NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (price >= 0), 
	CHECK (stock_quantity >= 0), 
	CHECK (status IN ('Active', 'Inactive')), 
	UNIQUE (product_code)
) ENGINE=InnoDB;

CREATE TABLE users (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(120) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	`role` VARCHAR(10) NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (role IN ('Admin', 'Sales')), 
	UNIQUE (email)
) ENGINE=InnoDB;

CREATE TABLE sales_orders (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	order_number VARCHAR(40) NOT NULL, 
	customer_id INTEGER NOT NULL, 
	order_date DATE NOT NULL, 
	status VARCHAR(12) NOT NULL, 
	discount_percentage NUMERIC(5, 2) NOT NULL, 
	subtotal NUMERIC(16, 2) NOT NULL, 
	discount_amount NUMERIC(16, 2) NOT NULL, 
	grand_total NUMERIC(16, 2) NOT NULL, 
	created_by INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (discount_percentage BETWEEN 0 AND 20), 
	CHECK (status IN ('Draft', 'Confirmed', 'Cancelled')), 
	UNIQUE (order_number), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
) ENGINE=InnoDB;

CREATE TABLE sales_order_items (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	order_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity INTEGER NOT NULL, 
	rate NUMERIC(14, 2) NOT NULL, 
	amount NUMERIC(16, 2) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (order_id, product_id), 
	CHECK (quantity > 0), 
	CHECK (rate >= 0), 
	CHECK (amount >= 0), 
	FOREIGN KEY(order_id) REFERENCES sales_orders (id), 
	FOREIGN KEY(product_id) REFERENCES products (id)
) ENGINE=InnoDB;

CREATE TABLE stock_movements (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	product_id INTEGER NOT NULL, 
	movement_type VARCHAR(20) NOT NULL, 
	quantity_change INTEGER NOT NULL, 
	order_id INTEGER, 
	reason VARCHAR(255) NOT NULL, 
	created_by INTEGER NOT NULL, 
	timestamp DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(order_id) REFERENCES sales_orders (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
) ENGINE=InnoDB;

CREATE INDEX ix_customers_status ON customers (status);

CREATE INDEX ix_customers_name ON customers (name);

CREATE INDEX ix_products_name ON products (name);

CREATE INDEX ix_products_category ON products (category);

CREATE INDEX ix_products_status ON products (status);

CREATE INDEX ix_sales_orders_customer_id ON sales_orders (customer_id);

CREATE INDEX ix_sales_orders_created_by ON sales_orders (created_by);

CREATE INDEX ix_sales_orders_status ON sales_orders (status);

CREATE INDEX ix_sales_orders_order_date ON sales_orders (order_date);

CREATE INDEX ix_sales_order_items_product_id ON sales_order_items (product_id);

CREATE INDEX ix_sales_order_items_order_id ON sales_order_items (order_id);

CREATE INDEX ix_stock_movements_product_id ON stock_movements (product_id);

CREATE INDEX ix_stock_movements_order_id ON stock_movements (order_id);

CREATE INDEX ix_stock_movements_timestamp ON stock_movements (timestamp);
