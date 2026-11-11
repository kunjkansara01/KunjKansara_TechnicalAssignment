-- =============================================================================
-- Sales Order & Inventory Management - database schema (MySQL 8)
--
-- Run against the empty database:
--   Git Bash / cmd : mysql -u sales_app -p sales_inventory < sql/schema.sql
--   PowerShell     : mysql -u sales_app -p sales_inventory -e "source sql/schema.sql"
--
-- Conventions
--   * Every table uses InnoDB so foreign keys and transactions work.
--   * Money columns are DECIMAL, never FLOAT, so totals are exact.
--   * Foreign keys use ON DELETE RESTRICT: a row that is still referenced
--     (a customer with orders, a product on an order) cannot be deleted.
-- =============================================================================

-- Drop in reverse dependency order so the script can be re-run during
-- development. Child tables go first because they hold the foreign keys.
DROP TABLE IF EXISTS stock_movements;
DROP TABLE IF EXISTS sales_order_items;
DROP TABLE IF EXISTS sales_orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS users;


-- -----------------------------------------------------------------------------
-- users: people who can log in. role decides what they may do.
-- -----------------------------------------------------------------------------
CREATE TABLE users (
    id            INT           NOT NULL AUTO_INCREMENT,
    name          VARCHAR(100)  NOT NULL,
    email         VARCHAR(150)  NOT NULL,
    password_hash VARCHAR(255)  NOT NULL,           -- bcrypt hash, never plaintext
    role          ENUM('admin', 'sales') NOT NULL DEFAULT 'sales',
    created_at    TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- customers: who we sell to. Inactive customers stay for history but cannot
-- be picked on new orders.
-- -----------------------------------------------------------------------------
CREATE TABLE customers (
    id         INT          NOT NULL AUTO_INCREMENT,
    name       VARCHAR(150) NOT NULL,
    email      VARCHAR(150) NULL,
    mobile     VARCHAR(20)  NULL,
    city       VARCHAR(100) NULL,
    is_active  BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    INDEX idx_customers_name (name),
    INDEX idx_customers_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- products: what we sell. stock_quantity is the current on-hand count and is
-- only changed by the backend together with a stock_movements row.
-- -----------------------------------------------------------------------------
CREATE TABLE products (
    id             INT           NOT NULL AUTO_INCREMENT,
    product_code   VARCHAR(50)   NOT NULL,
    name           VARCHAR(150)  NOT NULL,
    category       VARCHAR(100)  NULL,
    price          DECIMAL(10,2) NOT NULL,
    stock_quantity INT           NOT NULL DEFAULT 0,
    is_active      BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_products_code (product_code),
    INDEX idx_products_category (category),
    CONSTRAINT chk_products_price_non_negative CHECK (price >= 0),
    CONSTRAINT chk_products_stock_non_negative CHECK (stock_quantity >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- sales_orders: one row per order header. Totals are stored so reports do not
-- have to recompute them; the backend writes them from the line items.
-- -----------------------------------------------------------------------------
CREATE TABLE sales_orders (
    id                  INT           NOT NULL AUTO_INCREMENT,
    order_number        VARCHAR(30)   NOT NULL,
    customer_id         INT           NOT NULL,
    order_date          DATE          NOT NULL,
    status              ENUM('Draft', 'Confirmed', 'Cancelled') NOT NULL DEFAULT 'Draft',
    discount_percentage DECIMAL(5,2)  NOT NULL DEFAULT 0.00,
    subtotal            DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    discount_amount     DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    grand_total         DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    created_by          INT           NOT NULL,
    created_at          TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                      ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_sales_orders_number (order_number),
    INDEX idx_sales_orders_status (status),
    INDEX idx_sales_orders_date (order_date),
    INDEX idx_sales_orders_customer (customer_id),
    INDEX idx_sales_orders_created_by (created_by),

    CONSTRAINT chk_sales_orders_discount_range
        CHECK (discount_percentage >= 0 AND discount_percentage <= 100),

    -- A customer with orders cannot be deleted (RESTRICT).
    CONSTRAINT fk_sales_orders_customer
        FOREIGN KEY (customer_id) REFERENCES customers (id)
        ON DELETE RESTRICT ON UPDATE CASCADE,

    -- The user who created the order must keep existing (RESTRICT).
    CONSTRAINT fk_sales_orders_created_by
        FOREIGN KEY (created_by) REFERENCES users (id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- sales_order_items: one row per product line on an order.
-- rate is the price at the time of ordering, copied from products so later
-- price changes do not alter old orders. amount = quantity * rate.
-- -----------------------------------------------------------------------------
CREATE TABLE sales_order_items (
    id             INT           NOT NULL AUTO_INCREMENT,
    sales_order_id INT           NOT NULL,
    product_id     INT           NOT NULL,
    quantity       INT           NOT NULL,
    rate           DECIMAL(10,2) NOT NULL,
    amount         DECIMAL(12,2) NOT NULL,

    PRIMARY KEY (id),
    -- The same product may appear only once per order.
    UNIQUE KEY uq_order_items_order_product (sales_order_id, product_id),
    INDEX idx_order_items_product (product_id),

    CONSTRAINT chk_order_items_quantity_positive CHECK (quantity > 0),

    -- Lines belong to their order: deleting a (draft) order removes its lines.
    CONSTRAINT fk_order_items_order
        FOREIGN KEY (sales_order_id) REFERENCES sales_orders (id)
        ON DELETE CASCADE ON UPDATE CASCADE,

    -- A product on any order cannot be deleted (RESTRICT).
    CONSTRAINT fk_order_items_product
        FOREIGN KEY (product_id) REFERENCES products (id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- -----------------------------------------------------------------------------
-- stock_movements: audit trail of every change to products.stock_quantity.
-- quantity_change is positive for stock in, negative for stock out.
-- sales_order_id is filled only for order_confirm / order_cancel rows.
-- -----------------------------------------------------------------------------
CREATE TABLE stock_movements (
    id              INT          NOT NULL AUTO_INCREMENT,
    product_id      INT          NOT NULL,
    movement_type   ENUM('opening', 'order_confirm', 'order_cancel', 'adjustment') NOT NULL,
    quantity_change INT          NOT NULL,
    sales_order_id  INT          NULL,
    reason          VARCHAR(255) NULL,
    created_by      INT          NOT NULL,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    INDEX idx_stock_movements_product (product_id),
    INDEX idx_stock_movements_order (sales_order_id),
    INDEX idx_stock_movements_created_at (created_at),

    CONSTRAINT fk_stock_movements_product
        FOREIGN KEY (product_id) REFERENCES products (id)
        ON DELETE RESTRICT ON UPDATE CASCADE,

    -- Keep the audit trail: an order with stock movements cannot be deleted.
    CONSTRAINT fk_stock_movements_order
        FOREIGN KEY (sales_order_id) REFERENCES sales_orders (id)
        ON DELETE RESTRICT ON UPDATE CASCADE,

    CONSTRAINT fk_stock_movements_created_by
        FOREIGN KEY (created_by) REFERENCES users (id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
