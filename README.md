# Sales Order & Inventory Management

A small web application for recording customers, products and sales orders,
with stock that is deducted when an order is confirmed and restored when it
is cancelled. Built as a hiring assignment with a deliberately simple stack
and plain, readable code.

| Layer | Choice |
|-------|--------|
| Backend | Python 3.11, Flask 3 |
| Database | MySQL 8, accessed with `mysql-connector-python` and plain SQL |
| Frontend | Server-rendered Jinja templates, vanilla HTML/CSS/JavaScript |
| Auth | Flask session cookie, bcrypt password hashes |
| Tests | pytest against a separate test database |

## Features

- **Login and roles.** Two roles: `admin` (everything) and `sales` (view
  active customers and products, manage only their own orders). Web pages
  redirect to login; API calls get `401`/`403` JSON.
- **Customers.** Search by name, email or mobile; active/inactive filter;
  admin create, edit, deactivate and delete. Delete is refused with a clear
  message when any order references the customer.
- **Products.** Search by code or name, filter by category and status,
  unique product code, non-negative price and stock. Admin-only
  **Adjust Stock** (+/- with a mandatory reason) writes a stock movement in
  the same transaction. Delete is refused when order lines or stock movements
  reference the product.
- **CSV import** of products (admin). Every row is validated and every error
  is reported with its row number; if any row fails nothing is imported.
- **Sales orders.** Draft orders with multiple items, discount 0 to 20
  percent, order numbers like `SO-2026-0001`. All money is calculated on the
  server with `Decimal`. Drafts can be edited; Confirmed and Cancelled orders
  are read-only.
- **Confirm / cancel** in a single database transaction each. Confirm locks
  the product rows, checks every item's stock first, and either deducts all
  or changes nothing. Cancelling a confirmed order restores stock.
- **Reports** (admin): Customer Sales Summary, Product Sales Summary, Low
  Stock, Stock Movement History.
- **JSON API** under `/api` that reuses the same service functions as the web
  pages. See [API_EXAMPLES.md](API_EXAMPLES.md).
- **Stock audit trail.** Every change to a product's stock has a row in
  `stock_movements` saying what, how much, why and who.

## Project structure

```
app/
  __init__.py        create_app(): config, blueprints, error handlers, filters
  config.py          reads .env
  db.py              one MySQL connection per request
  decorators.py      @login_required, @admin_required
  models.py          one plain function per SQL query (never commits)
  services/          business rules; decide when to commit / roll back
    auth_service.py        bcrypt login check
    customer_service.py    validation, delete rules
    product_service.py     validation, Decimal parsing, stock adjustment
    order_service.py       totals, validation, create/edit, confirm/cancel
    report_service.py      report filter parsing
    import_service.py      CSV validation and all-or-nothing import
  routes/            thin Flask blueprints: parse request, call service, render
  templates/         Jinja pages
  static/            style.css, js/order_form.js
sql/
  schema.sql         tables, constraints, foreign keys
  seed.sql           demo users, customers, products, opening stock
  setup_database.sql         one-time: create database + app user
  setup_test_database.sql    one-time: create the pytest database
  queries.sql        five standalone report queries
tests/               pytest suite (see TESTING.md)
tools/check_db.py    prints whether .env can reach MySQL
samples/             valid_products.csv, invalid_products.csv for import
docs/DEBUGGING.md    the calculate_total debugging exercise
debugging.py         corrected calculate_total with defined edge cases
```

Rule of thumb used throughout: **routes** read the request and render,
**services** hold the rules and own transactions, **models** run SQL.

## Setup

Prerequisites: Python 3.11 and MySQL 8 running locally.

1. **Create the virtual environment and install dependencies**

   ```bash
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. **Create the database and application user** (needs the MySQL root
   password once). Edit the password in `sql/setup_database.sql` first.

   ```bash
   mysql -u root -p -e "source sql/setup_database.sql"
   ```

3. **Configure the app.** Copy `.env.example` to `.env` and fill in
   `SECRET_KEY` and the `DB_*` values. `.env` is ignored by git.

   ```bash
   copy .env.example .env
   ```

   Check the connection:

   ```bash
   python tools/check_db.py
   ```

4. **Load the schema and demo data**

   ```bash
   mysql -u sales_app -p sales_inventory -e "source sql/schema.sql"
   mysql -u sales_app -p sales_inventory -e "source sql/seed.sql"
   ```

   `schema.sql` drops and recreates every table, so re-running it resets the
   data.

5. **Run**

   ```bash
   python run.py
   ```

   Open http://127.0.0.1:5000. Set `FLASK_DEBUG=1` in `.env` for auto-reload
   and browser tracebacks during development only.

6. **Test** (one-time: create the test database with
   `mysql -u root -p -e "source sql/setup_test_database.sql"`)

   ```bash
   pytest
   ```

   Details in [TESTING.md](TESTING.md).

## Sample accounts

| Role  | Email               | Password    |
|-------|---------------------|-------------|
| admin | admin@example.com   | `Admin@123` |
| sales | sales@example.com   | `Sales@123` |

The seed also creates five customers (one inactive), eight products (one
inactive with zero stock) and an opening stock movement per product.

## Schema

```
users ──────────────┐
  │ created_by      │ created_by
  ▼                 ▼
sales_orders ◄──── stock_movements ────► products
  │ customer_id        (sales_order_id NULL        ▲
  ▼                     for opening/adjustment)    │ product_id
customers                                          │
  ▲                                                │
  └── sales_orders ──► sales_order_items ──────────┘
                        (UNIQUE order+product)
```

| Table | Purpose | Notes |
|-------|---------|-------|
| `users` | Logins | `role ENUM('admin','sales')`, bcrypt `password_hash` |
| `customers` | Who we sell to | `is_active` flag; indexed on name and status |
| `products` | What we sell | `product_code` unique; `CHECK price >= 0`, `CHECK stock_quantity >= 0` |
| `sales_orders` | Order header | `order_number` unique; status Draft/Confirmed/Cancelled; stored subtotal, discount, grand total |
| `sales_order_items` | Order lines | `UNIQUE (sales_order_id, product_id)`; `CHECK quantity > 0`; `rate` copied from product |
| `stock_movements` | Audit trail | type opening / order_confirm / order_cancel / adjustment; signed `quantity_change` |

Foreign keys to `customers`, `products` and `users` are `ON DELETE RESTRICT`.
`sales_order_items` to its order is `ON DELETE CASCADE` (a deleted draft takes
its lines with it). `stock_movements` to its order is `RESTRICT` so an order
that moved stock can never be deleted.

Invariant maintained by the code: for every product,
`stock_quantity = SUM(stock_movements.quantity_change)`.

## Key design decisions

**Money is `Decimal`, rounded half-up to two places, on the server only.**
Floats cannot represent 0.1 exactly; `Decimal("0.1") + Decimal("0.2")` is
exactly `0.30`. The browser shows a live preview but every figure it sends is
ignored and recalculated from the database.

**The rate is stored on the order item.** `sales_order_items.rate` is a copy
of the product's price at the moment the order was saved. If the price is
changed next month, old orders still show what the customer actually agreed
to, and reports over past periods stay correct. Reading the price through a
join would silently rewrite history.

**`SELECT ... FOR UPDATE` for stock.** Confirming an order reads each
product row with `FOR UPDATE` inside the transaction that will write it. The
lock lasts until commit, so a second request for the same product waits at
the read, then sees the already-reduced stock and refuses. Without the lock
two users could both read "1 left", both pass the check, and both sell it.
Products are locked in `product_id` order so two orders sharing products
cannot deadlock. The order row is locked the same way, which is why a
repeated Confirm sees the new status and does nothing.
`tests/test_order_status.py::test_confirm_waits_for_competing_lock...`
demonstrates this with a second connection.

**`ON DELETE RESTRICT` plus deactivation.** Deleting a customer or product
that appears on an order would either break the order or destroy history.
The database refuses, the service checks first to give a friendly message,
and the recommended action is to deactivate instead. Inactive records stay
in reports but cannot be chosen on new orders.

**Ownership is enforced in SQL, not in templates.** `models.get_order` and
`models.list_orders` add `AND created_by = <user>` for sales users. A sales
user can never load another user's order data; the route then answers `403`
if the order exists and `404` if it does not.

**All-or-nothing everywhere.** Order create/edit, confirm, cancel, stock
adjustment and CSV import each run as one transaction. Models never commit;
the calling service commits or rolls back.

**Validation lives in services and is shared.** The JSON API converts its
body into the same form structure the web page sends and calls the same
`validate_order_form`, so there is exactly one copy of each rule.

## Assumptions

- Prices and totals are in a single currency; no tax is applied.
- Discount is a percentage of the subtotal, capped at 20 percent, applied at
  order level (not per line).
- Editing a draft refreshes item rates to current prices, because a draft has
  not been agreed with the customer yet. Confirmed orders freeze the rate.
- Order numbers restart at 0001 each calendar year, based on `order_date`.
- A product created with opening stock gets an `opening` movement; a product
  created with zero stock gets none.
- The user's role is read from the session, not re-queried on each request.
  A role change takes effect at the user's next login.
- Reports run on the live tables; there is no separate reporting store.
- Sales users may view the stock history of active products (read-only).

## Known limitations

- No user management screen; users are created in `seed.sql` or by SQL.
- No pagination on the web list pages (the API's product list is paged).
- The CSV import is capped at 2 MB and 5000 rows per file.
- Stock Movement History shows at most 500 rows.
- No CSRF tokens on forms. State-changing routes are POST-only and the
  session cookie is `SameSite=Lax`, which blocks cross-site POSTs in modern
  browsers, but a full CSRF token scheme would be the next step.
- Login has no rate limiting or account lockout.
- Order confirmation does not reserve stock for drafts; a draft can be saved
  for more than is in stock and will be refused at confirm time.
- Single-currency, no tax, no shipping, no partial fulfilment.
- The development server (`python run.py`) is not for production use.
