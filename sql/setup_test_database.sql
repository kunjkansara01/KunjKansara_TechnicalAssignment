-- One-time setup for the pytest database. Run as root:
--   mysql -u root -p -e "source sql/setup_test_database.sql"
--
-- The tests create and drop tables inside this database on every run, so it
-- must be separate from the real one. sales_app gets the same rights here as
-- on sales_inventory; no password change is involved.

CREATE DATABASE IF NOT EXISTS sales_inventory_test
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

GRANT ALL PRIVILEGES ON sales_inventory_test.* TO 'sales_app'@'localhost';

FLUSH PRIVILEGES;
