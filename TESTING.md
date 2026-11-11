# Running the tests

The suite uses pytest and a **separate MySQL test database**. Nothing in the
real `sales_inventory` database is touched.

## One-time setup

1. Install dependencies in the project venv (already done if the app runs):

   ```bash
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Create the test database and give the app user rights on it. This needs
   the MySQL root password once:

   ```bash
   mysql -u root -p -e "source sql/setup_test_database.sql"
   ```

   That script creates `sales_inventory_test` and grants `sales_app` the same
   rights it has on the real database. The connection details come from the
   same `.env` as the app; only the database name differs.

   To use a different name, set `TEST_DB_NAME` in the environment before
   running pytest. The fixture refuses to run if the test name equals the real
   `DB_NAME`.

## Run

From the project folder with the venv active:

```bash
pytest
```

Useful variations:

```bash
pytest -q                          # quiet
pytest tests/test_assignment.py    # just the assignment's required cases
pytest -k confirm                  # tests whose name contains "confirm"
pytest -x                          # stop at the first failure
```

## What happens on each run

`tests/conftest.py` has a session-scoped fixture that:

1. connects to the test database,
2. runs `sql/schema.sql` (drops and recreates every table),
3. runs `sql/seed.sql` (2 users, 5 customers, 8 products, opening stock).

Every test therefore starts from the same seed. Tests that create orders or
products also clean up after themselves so they can run in any order.

## Test files

| File | Covers |
|------|--------|
| `test_assignment.py` | The nine required cases: multi-item totals, bad quantity, bad discount, confirm OK, confirm with one short item, repeated confirm, cancel restores once, 403 on another user's order, CSV with one bad row imports nothing |
| `test_auth.py` | Login, logout, `login_required`, `admin_required`, error pages |
| `test_customers.py` | Customer list, search, create, edit, deactivate, delete rules |
| `test_products.py` | Product list, filters, validation, delete rules, stock adjustment |
| `test_orders.py` | Order creation, Decimal calculations, validation, draft editing, ownership |
| `test_order_status.py` | Confirm and cancel transactions, including a FOR UPDATE lock-wait test |
| `test_api.py` | JSON endpoints and status codes |
| `test_reports.py` | Admin reports, including the no-double-counting check |
| `test_import.py` | CSV import validation and all-or-nothing behaviour |
| `test_debugging.py` | The corrected `calculate_total` from the debugging exercise (pure unit tests) |

## Troubleshooting

- **"Cannot open test database"**: run the setup script in step 2.
- **"Access denied for user 'sales_app'"**: `.env` and MySQL disagree on the
  password. `python tools/check_db.py` shows which settings are in use.
- **"Can't connect to MySQL server"**: the MySQL Windows service is not
  running. Start it from Services, or from an administrator PowerShell with
  `net start MySQL84` (the service name depends on the installed version).
- The lock-wait test (`test_confirm_waits_for_competing_lock...`) deliberately
  takes about two seconds; that is expected.
