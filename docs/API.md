# API examples

All endpoints return JSON except successful DELETE, which returns HTTP 204. Monetary values are decimal strings. Authentication uses a session cookie. Run these requests from the same browser origin or an API client that retains cookies.

First call `GET /api/session`. Retain its `csrf_token` and send it as `X-CSRF-Token` on every POST, PUT or DELETE. Login rotates the token. Update your client with the new token returned by login.

```http
POST /api/login
Content-Type: application/json
X-CSRF-Token: <token from session>

{"email":"admin@example.test","password":"<your configured password>"}
```

Successful login returns HTTP 200 with `user` (id, name, email, role) and `csrf_token`. Logout uses `POST /api/logout`.

```http
GET /api/products?search=KEY&page=1&page_size=25
```

```json
{"items":[{"id":1,"product_code":"PRD-001","name":"Keyboard","category":"Accessories","price":"1500.00","stock_quantity":20,"status":"Active"}],"total":1,"page":1,"page_size":25}
```

Admins may add `status=Active` or `status=Inactive` and `category=Accessories`. Sales users are always restricted to active records. Customer search uses `GET /api/customers?search=buyer&status=Active` and supports the same pagination.

```http
POST /api/orders
Content-Type: application/json
X-CSRF-Token: <current token>

{"customer_id":1,"order_date":"2026-11-07","discount_percentage":10,"items":[{"product_id":1,"quantity":2},{"product_id":2,"quantity":3}]}
```

Response HTTP 201 includes the generated `id`, unique `order_number`, `status="Draft"`, `subtotal="4500.00"`, `discount_amount="450.00"`, `grand_total="4050.00"`, `created_by` and item records with saved rates and amounts.

| Method | Route | Behavior |
| --- | --- | --- |
| GET | `/api/orders` | Accessible orders and items |
| GET | `/api/orders/1` | Accessible order and items |
| PUT | `/api/orders/1` | Replace draft using the create request structure |
| POST | `/api/orders/1/confirm` | Confirm and deduct stock atomically |
| POST | `/api/orders/1/cancel` | Cancel and restore stock when applicable |
| POST | `/api/customers` | Admin creates customer |
| PUT / DELETE | `/api/customers/1` | Admin edits or safely deletes customer |
| POST | `/api/products` | Admin creates product and opening stock |
| PUT / DELETE | `/api/products/1` | Admin edits master data or safely deletes product |
| POST | `/api/products/1/adjust` | Admin adjusts stock with reason |
| POST | `/api/products/import` | Admin uploads multipart file field `file` |
| GET | `/api/reports/customers?start=2026-11-01&end=2026-11-30` | Admin customer summary |
| GET | `/api/reports/products` | Admin product summary |
| GET | `/api/reports/low-stock?threshold=10` | Admin low-stock report |
| GET | `/api/reports/movements` | Admin movement ledger |

Customer payload example is `{"name":"Acme","email":"buyer@example.test","mobile":"9000000000","city":"Mumbai","status":"Active"}`. Product payload example is `{"product_code":"NEW-01","name":"Monitor","category":"Electronics","price":"12000.00","stock_quantity":5,"status":"Active"}`. Omit `stock_quantity` when editing a product. Adjustment payload is `{"quantity_change":-2,"reason":"Damaged units removed"}`.

Reports return `{"items":[...]}`. CSV success returns HTTP 201 with `{"imported":2}`. Validation failure returns HTTP 400, for example `{"error":"Import rejected. No products were imported.","details":[{"row":3,"reason":"Duplicate product code"}]}`.

HTTP status meanings are 400 invalid data, 401 unauthenticated, 403 denied access or invalid CSRF, 404 missing resource, 409 business conflict or database constraint, 413 oversized upload, 415 incorrect content type, and 503 temporary database failure. Internal exceptions produce a generic 500 response and are logged on the server.
