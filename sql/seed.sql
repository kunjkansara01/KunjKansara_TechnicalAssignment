-- =============================================================================
-- Sales Order & Inventory Management - demo seed data
--
-- Run AFTER sql/schema.sql on the same database:
--   Git Bash / cmd : mysql -u sales_app -p sales_inventory < sql/seed.sql
--   PowerShell     : mysql -u sales_app -p sales_inventory -e "source sql/seed.sql"
--
-- Demo login credentials (bcrypt hashes below were generated from these):
--   admin@example.com / Admin@123   (role: admin)
--   sales@example.com / Sales@123   (role: sales)
--
-- IDs are written explicitly so the foreign keys further down are easy to
-- follow. schema.sql drops and recreates every table, so IDs start at 1.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- users
-- -----------------------------------------------------------------------------
INSERT INTO users (id, name, email, password_hash, role) VALUES
    (1, 'Admin User', 'admin@example.com',
        '$2b$12$GBc7tRNjWG1h2UgYok4NnugDrEystHgMN0BISvCveRKRmmeZ5xMHi', 'admin'),
    (2, 'Sales User', 'sales@example.com',
        '$2b$12$fMcNuOc7wHstikPtT1I80uSgwIgeMLrxSgnfARGsgbnmBYA6yHa3e', 'sales');


-- -----------------------------------------------------------------------------
-- customers (5). One is inactive to exercise the is_active filter.
-- -----------------------------------------------------------------------------
INSERT INTO customers (id, name, email, mobile, city, is_active) VALUES
    (1, 'Sunrise Traders',        'contact@sunrisetraders.in',  '9876500001', 'Mumbai',    TRUE),
    (2, 'Green Power Solutions',  'sales@greenpower.in',        '9876500002', 'Ahmedabad', TRUE),
    (3, 'Patel Electricals',      'info@patelelectricals.in',   '9876500003', 'Surat',     TRUE),
    (4, 'Metro Infra Projects',   'projects@metroinfra.in',     '9876500004', 'Pune',      TRUE),
    (5, 'Old Town Hardware',      'oldtown@example.in',         '9876500005', 'Nagpur',    FALSE);


-- -----------------------------------------------------------------------------
-- products (8). stock_quantity here must equal the opening movement below.
-- -----------------------------------------------------------------------------
INSERT INTO products (id, product_code, name, category, price, stock_quantity, is_active) VALUES
    (1, 'SP-540',   'Solar Panel 540W Mono PERC',      'Solar Panels',  12500.00, 120, TRUE),
    (2, 'SP-450',   'Solar Panel 450W Poly',           'Solar Panels',   9800.00,  80, TRUE),
    (3, 'INV-5K',   'String Inverter 5kW',             'Inverters',     42000.00,  25, TRUE),
    (4, 'INV-10K',  'String Inverter 10kW',            'Inverters',     78500.00,  10, TRUE),
    (5, 'BAT-150',  'Lithium Battery 150Ah',           'Batteries',     65000.00,  15, TRUE),
    (6, 'CBL-4MM',  'DC Solar Cable 4mm (100m roll)',  'Accessories',    3200.00,  60, TRUE),
    (7, 'MC4-PAIR', 'MC4 Connector Pair',              'Accessories',     150.00, 500, TRUE),
    (8, 'STR-GI',   'GI Mounting Structure (per kW)',  'Structures',     4500.00,   0, FALSE);


-- -----------------------------------------------------------------------------
-- stock_movements: one 'opening' row per product, recorded by the admin.
-- quantity_change equals the product's starting stock_quantity.
-- -----------------------------------------------------------------------------
INSERT INTO stock_movements (product_id, movement_type, quantity_change, sales_order_id, reason, created_by) VALUES
    (1, 'opening', 120, NULL, 'Opening stock', 1),
    (2, 'opening',  80, NULL, 'Opening stock', 1),
    (3, 'opening',  25, NULL, 'Opening stock', 1),
    (4, 'opening',  10, NULL, 'Opening stock', 1),
    (5, 'opening',  15, NULL, 'Opening stock', 1),
    (6, 'opening',  60, NULL, 'Opening stock', 1),
    (7, 'opening', 500, NULL, 'Opening stock', 1),
    (8, 'opening',   0, NULL, 'Opening stock', 1);
