-- One-time setup: creates the database and a dedicated application user.
-- Run as root:  mysql -u root -p < sql/setup_database.sql
-- Replace CHANGE_ME with the same password you put in .env (DB_PASSWORD).

CREATE DATABASE IF NOT EXISTS sales_inventory
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- The app connects as this user, not as root. It only has rights on its own
-- database, so a bug in the app cannot touch anything else on the server.
CREATE USER IF NOT EXISTS 'sales_app'@'localhost' IDENTIFIED BY 'CHANGE_ME';

GRANT ALL PRIVILEGES ON sales_inventory.* TO 'sales_app'@'localhost';

FLUSH PRIVILEGES;
