# JSON API examples

All endpoints live under `/api` and return JSON. The API shares its service
functions with the web pages, so validation rules and messages are identical.

Every response that was captured below came from the running development
server with the seed data loaded.

## Authentication

The API uses the same session cookie as the web pages. Log in once with the
form endpoint and save the cookie, then send it with every request.

```bash
curl -c cookies.txt -X POST -d "email=sales@example.com&password=Sales@123" http://127.0.0.1:5000/auth/login
```

Response: `HTTP 302` (redirect to the home page). The cookie is now in
`cookies.txt`. Add `-b cookies.txt` to every call below.

Demo users (from `sql/seed.sql`):

| Role  | Email             | Password  |
|-------|-------------------|-----------|
| admin | admin@example.com | Admin@123 |
| sales | sales@example.com | Sales@123 |

On Windows PowerShell use `curl.exe` (plain `curl` is an alias for
`Invoke-WebRequest`) and swap the single quotes in JSON bodies for a
here-string or escaped double quotes.

## Status codes

| Code | Meaning                                                         |
|------|-----------------------------------------------------------------|
| 200  | Success                                                         |
| 201  | Created (`POST /api/orders`)                                    |
| 400  | Validation failed; `errors` lists every problem                 |
| 401  | Not logged in                                                   |
| 403  | Logged in but not allowed: wrong role, or another user's order  |
| 404  | No such record                                                  |
| 409  | Business rule refused the action (wrong status, short on stock) |

Error bodies always look like `{"ok": false, "message": "..."}`, with an
`errors` list added for validation failures.

---

## GET /api/products

Active products only. Query string: `q` (code or name), `category`,
`page` (1-based), `per_page` (default 20, max 100).

```bash
curl -b cookies.txt "http://127.0.0.1:5000/api/products?q=inv&per_page=2"
```

```json
{
  "items": [
    {
      "category": "Inverters",
      "id": 4,
      "is_active": true,
      "name": "String Inverter 10kW",
      "price": "78500.00",
      "product_code": "INV-10K",
      "stock_quantity": 10
    },
    {
      "category": "Inverters",
      "id": 3,
      "is_active": true,
      "name": "String Inverter 5kW",
      "price": "42000.00",
      "product_code": "INV-5K",
      "stock_quantity": 25
    }
  ],
  "ok": true,
  "page": 1,
  "pages": 1,
  "per_page": 2,
  "total": 2
}
```
`HTTP 200`

Prices are strings so that two decimal places survive JSON exactly.

Without a cookie:

```bash
curl "http://127.0.0.1:5000/api/products"
```

```json
{
  "message": "Authentication required",
  "ok": false
}
```
`HTTP 401`

---

## GET /api/products/{id}

One product, used by the order form to show price and stock.

```bash
curl -b cookies.txt http://127.0.0.1:5000/api/products/1
```

```json
{
  "category": "Solar Panels",
  "id": 1,
  "is_active": true,
  "name": "Solar Panel 540W Mono PERC",
  "ok": true,
  "price": "12500.00",
  "product_code": "SP-540",
  "stock_quantity": 120
}
```
`HTTP 200`

Inactive product requested by a sales user (admins can still see it):

```bash
curl -b cookies.txt http://127.0.0.1:5000/api/products/8
```

```json
{
  "message": "Product not found.",
  "ok": false
}
```
`HTTP 404`

---

## POST /api/orders

Creates a Draft order. Body fields: `customer_id` (required),
`order_date` (optional, `YYYY-MM-DD`, defaults to today),
`discount_percentage` (optional, 0 to 20), `items` (at least one
`{product_id, quantity}`).

Rates and totals in the body are ignored. The server reads each product's
current price and calculates every figure with `Decimal`.

```bash
curl -b cookies.txt -H "Content-Type: application/json" \
  -d '{"customer_id":1,"order_date":"2026-03-15","discount_percentage":"10","items":[{"product_id":1,"quantity":2},{"product_id":7,"quantity":3}]}' \
  http://127.0.0.1:5000/api/orders
```

```json
{
  "created_by": {
    "id": 2,
    "name": "Sales User"
  },
  "customer": {
    "id": 1,
    "name": "Sunrise Traders"
  },
  "discount_amount": "2545.00",
  "discount_percentage": "10.00",
  "grand_total": "22905.00",
  "id": 150,
  "items": [
    {
      "amount": "25000.00",
      "product_code": "SP-540",
      "product_id": 1,
      "product_name": "Solar Panel 540W Mono PERC",
      "quantity": 2,
      "rate": "12500.00"
    },
    {
      "amount": "450.00",
      "product_code": "MC4-PAIR",
      "product_id": 7,
      "product_name": "MC4 Connector Pair",
      "quantity": 3,
      "rate": "150.00"
    }
  ],
  "ok": true,
  "order_date": "2026-03-15",
  "order_number": "SO-2026-0002",
  "status": "Draft",
  "subtotal": "25450.00"
}
```
`HTTP 201`

Validation failure (inactive customer, discount over 20, zero quantity,
duplicate product):

```bash
curl -b cookies.txt -H "Content-Type: application/json" \
  -d '{"customer_id":5,"discount_percentage":"25","items":[{"product_id":1,"quantity":0},{"product_id":1,"quantity":1}]}' \
  http://127.0.0.1:5000/api/orders
```

```json
{
  "errors": [
    "The selected customer is not available.",
    "Discount must be between 0 and 20 percent.",
    "Item 1 (SP-540): quantity must be a whole number greater than zero.",
    "Item 2: this product is already on the order. Change its quantity instead."
  ],
  "message": "Validation failed.",
  "ok": false
}
```
`HTTP 400`

Body that is not a JSON object:

```bash
curl -b cookies.txt -H "Content-Type: application/json" -d 'hello' http://127.0.0.1:5000/api/orders
```

```json
{
  "message": "Request body must be a JSON object.",
  "ok": false
}
```
`HTTP 400`

---

## GET /api/orders/{id}

One order with its items. A sales user can only fetch their own orders.
Another user's order returns 403; an id that does not exist returns 404.
The ownership check is inside the SQL, so the order's data is never read.

```bash
curl -b cookies.txt http://127.0.0.1:5000/api/orders/150
```

Returns the same shape as the create response (see above). `HTTP 200`

Another user's order, requested by the sales user:

```bash
curl -b cookies.txt http://127.0.0.1:5000/api/orders/17
```

```json
{
  "message": "You do not have access to this order.",
  "ok": false
}
```
`HTTP 403`

An id that does not exist:

```json
{
  "message": "Order not found.",
  "ok": false
}
```
`HTTP 404`

---

## POST /api/orders/{id}/confirm

Draft to Confirmed in one database transaction. Locks the order row and
every product row, checks all stock first, then deducts and writes one
`order_confirm` stock movement per item. Any shortfall rejects the whole
order and nothing changes.

```bash
curl -b cookies.txt -X POST http://127.0.0.1:5000/api/orders/150/confirm
```

```json
{
  "message": "Order SO-2026-0002 confirmed. Stock has been deducted.",
  "ok": true,
  "status": "Confirmed"
}
```
`HTTP 200`

Calling it again:

```json
{
  "message": "Order SO-2026-0002 is already Confirmed and cannot be confirmed.",
  "ok": false
}
```
`HTTP 409`

Insufficient stock (order SO-2026-0003 asked for 11 of a product with 10):

```bash
curl -b cookies.txt -X POST http://127.0.0.1:5000/api/orders/151/confirm
```

```json
{
  "message": "Cannot confirm SO-2026-0003 because of insufficient stock. INV-10K: need 11, only 10 in stock.",
  "ok": false
}
```
`HTTP 409`

---

## POST /api/orders/{id}/cancel

Draft to Cancelled changes only the status. Confirmed to Cancelled also puts
every quantity back and writes one `order_cancel` movement per item, in one
transaction.

```bash
curl -b cookies.txt -X POST http://127.0.0.1:5000/api/orders/150/cancel
```

```json
{
  "message": "Order SO-2026-0002 cancelled. Stock has been restored.",
  "ok": true,
  "status": "Cancelled"
}
```
`HTTP 200`

Calling it again:

```json
{
  "message": "Order SO-2026-0002 is already cancelled.",
  "ok": false
}
```
`HTTP 409`

---

## 403 for a role violation

Besides another user's order, a 403 appears when a sales user calls an
admin-only endpoint:

```bash
curl -b cookies.txt http://127.0.0.1:5000/api/admin/ping
```

```json
{
  "message": "Admin access required",
  "ok": false
}
```
`HTTP 403`
