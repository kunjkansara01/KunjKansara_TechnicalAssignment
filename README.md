# Ledger — Sales Order & Inventory Management

Fresher / Trainee assignment built in two phases. Phase 1 implements authentication, master data, draft orders, transactional stock handling and the web interface. Phase 2 adds reporting, CSV import, automated verification, SQL queries and submission materials.

## Run locally

Supported runtime is Python 3.11+ and MySQL 8.4 with InnoDB. The interface uses plain HTML, CSS and JavaScript. Currency is INR. The app binds to localhost.

1. Install Python and MySQL. Create an empty database and a dedicated application user using a MySQL administrator account.

   ```sql
   CREATE DATABASE sales_inventory CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
   CREATE USER 'inventory'@'localhost' IDENTIFIED BY 'choose-your-own-password';
   GRANT ALL PRIVILEGES ON sales_inventory.* TO 'inventory'@'localhost';
   ```

2. Open a terminal in this project directory.

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   Copy-Item .env.example .env
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

3. Edit `.env` with the database connection, generated secret key and two demo passwords of at least 10 characters. URL-encode special characters in the database password. Keep `.env` private.

4. Create the schema and sample data, then start the server.

   ```powershell
   python -m flask --app run init-db
   python -m flask --app run seed
   python run.py
   ```

5. Open http://127.0.0.1:5000. Sign in as `admin@example.test` or `sales@example.test` using the corresponding password you set. Re-running seed adds missing sample records without resetting passwords or stock. For SQL-based setup, `sql/schema.sql` provides the same schema. Use either schema creation method, then seed.

On macOS/Linux, activate the environment with `source .venv/bin/activate`. The remaining Python commands are identical.

## Structure and design

| Location | Purpose |
| --- | --- |
| `app/models.py` | Six entities, foreign keys, indexes and database constraints |
| `app/services.py` | Shared validation, financial calculations, order transitions and CSV import |
| `app/__init__.py` | Application factory, authenticated API routes, reports and CLI setup |
| `app/static/` and `app/templates/` | Responsive interface and fetch-based interactions |
| `tests/` | API, business rule, permissions and concurrency tests |
| `sql/` | MySQL schema and five reporting queries |
| `debugging.py` | Corrected debugging exercise |

Each order belongs to one customer and one creator. It has multiple items, each referencing one product. Each stock movement references a product and user, and optionally an order. Foreign keys prevent deletion of referenced master records. Inactivation preserves history. Unique constraints protect email, product code, order number and the order/product pair. Status, dates and foreign keys are indexed. Money uses fixed-point decimal columns.

The server ignores browser-supplied rates, totals, owner and status. An item's initial rate comes from the product. Editing an existing draft retains rates for products already on that draft. Newly added products use current prices. Monetary values use Decimal and ROUND_HALF_UP to two places. Input prices and discounts allow at most two decimal places. Quantities must be positive integers. Order numbers use a random 96-bit identifier backed by a unique constraint.

Confirmation locks the order row, then all involved product rows in ascending ID order with `SELECT ... FOR UPDATE`. It updates stock, movement records and status in one transaction. Any failure rolls everything back. The same order lock serializes repeated confirmation and cancellation requests. Repeating the already-completed action returns the current order without another stock movement. Product lock order reduces deadlock risk. Database conflicts return HTTP 503 and can be retried. MySQL uses READ COMMITTED isolation so reads after an acquired row lock see the latest committed item data. The application uses one transaction per mutation and closes each request's session.

Only admins may change master data, import stock, adjust stock or view reports. Sales users can access only their own orders. Passwords use Werkzeug's salted scrypt hashing. Signed session cookies are HTTP-only and SameSite=Lax. Every mutation, including login, requires a session CSRF token. Errors return JSON without tracebacks. HTML output escapes stored values and the page has a restrictive content security policy.

Customer sales aggregate orders before joining customers, avoiding multiplication by item count. The optional date range is inclusive and preserves customers with zero confirmed orders. Product sales use gross item amounts. Cancelling an order removes it from both sales reports.

CSV imports require the exact sample header, UTF-8 encoding and a maximum upload size of 2 MB. Product codes are normalized to uppercase. Validation collects row numbers and reasons. All rows and opening stock movements commit together. A concurrent duplicate insert is also rejected by the database and rolled back.

## Tests

```powershell
python -m pytest -q
```

The default suite uses temporary SQLite databases for fast rule checks and skips the MySQL concurrency test. To verify actual locking, create a separate disposable database named `sales_inventory_test`, grant the test account access, and run the same tests against MySQL.

```powershell
$env:TEST_DATABASE_URL = 'mysql+pymysql://inventory:your-password@localhost:3306/sales_inventory_test'
python -m pytest -q
Remove-Item Env:TEST_DATABASE_URL
```

The suite recreates its tables before and after every test. It refuses MySQL test databases whose name does not end in `_test`. Never point this setting at a database you need to retain.

## Scope and assumptions

- One currency, one stock location, whole-number quantities and at most 100 items per order.
- Taxes, purchasing, delivery and payments are excluded as specified.
- Confirmed and cancelled orders are read-only. Confirmation and cancellation operate on the saved order. Save draft edits first.
- A customer and every product must be active when creating, editing or confirming an order. Cancellation remains available after deactivation.
- All products, including inactive ones, appear in the admin low-stock report. Sales users see active master records only.
- Stock can change through opening balances, CSV import, explicit adjustments, confirmation and cancellation. Product editing cannot bypass the movement ledger.
- No registration or password reset flow is included. Demo accounts are created by the seed command.
- The local development server is intended for the assignment demo. Public hosting is optional and has not been configured.

## Submission

See `docs/API.md`, `docs/DEBUGGING.md`, `docs/DEMO_SCRIPT.md`, `AI_USAGE.md` and `docs/VERIFICATION.md`. Submit this Git repository or an archive preserving `.git`. Replace the generic folder name with `FullName_TechnicalAssignment`. Git commits currently use the neutral identity `Assignment Developer <developer@example.test>`.

Review the implementation and practice the demo before submitting. The interview requires explaining transactions, permissions, JavaScript, SQL and making a small live change.

## References consulted

- [SQLAlchemy session API](https://docs.sqlalchemy.org/en/20/orm/session_api.html)
- [Flask security guidance](https://flask.palletsprojects.com/en/stable/web-security/)
- [MySQL Windows installation](https://dev.mysql.com/doc/refman/8.4/en/windows-installation.html)

## This computer

The prepared project is at `E:\Project`. Run `powershell -ExecutionPolicy Bypass -File E:\Project\start.ps1`, then open http://127.0.0.1:5000. The private `.env` contains the two demo passwords. MySQL runs locally on port 3307 from `.local`, which is excluded from Git and the submission archive. The application environment is `.venv`.

## Optional browser verification and demo recording

Install `playwright` and `imageio-ffmpeg` in the environment and run `python -m playwright install ffmpeg`. Microsoft Edge must be installed. With the app running, `python tools/record_demo.py` records the live walkthrough and creates `demo/Assignment_Demo.mp4`. It creates demonstration customers, orders, stock adjustments and imported products. Use fresh sample CSV codes when repeating the recording. The supplied video is captioned and has no voice narration. Movement timestamps use UTC.
