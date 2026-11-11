# AI Usage

## Tools used

- [TODO: tool name and version]

## How it was used

I designed the system before any code was written: the order lifecycle
(Draft → Confirmed → Cancelled and the stock effect of each transition), the
six-table schema (order header and lines split, an append-only
`stock_movements` ledger, the rate snapshotted on each order item), the
routes / services / db module structure, and the validation and security
rules. Each prompt I gave the tool stated the rules to implement rather than
asking what the rules should be.

The AI tool was used to implement that design faster: generating Flask
routes, service functions and templates to my specification, writing
repetitive CRUD, validation and test code, and helping debug setup and test
failures. Where it proposed an implementation detail I had not specified
(for example, locking product rows in id order to avoid deadlocks), I kept
it only after reading and testing it.

## Example prompts

1. "Implement confirm and cancel in order_service using ONE database
   transaction each. Confirm: only from Draft; lock the product rows with
   SELECT ... FOR UPDATE; if ANY item has insufficient stock, roll back and
   reject the whole confirmation listing the shortfall; otherwise deduct
   stock, write one stock_movement per item (order_confirm, negative qty,
   linked to the order), set status Confirmed. Cancel: Draft→Cancelled with
   no stock effect; Confirmed→Cancelled restores stock inside a transaction
   with order_cancel movements. Repeated confirm/cancel requests must be
   no-ops with a clear error (check status inside the locked transaction).
   Confirmed/Cancelled orders are read-only."
2. "Build product management the same way: search by code/name, filter by
   category and status, unique product_code validation, reject negative
   price/stock. Delete blocked if referenced by any order or stock movement.
   Add an admin-only "Adjust Stock" action: +/- quantity with a MANDATORY
   reason, writes a stock_movement, rejects adjustments that would go
   negative."
3. "Write a pytest suite with a test MySQL database fixture covering exactly:
   multi-item order with discount → correct subtotal/grand total;
   zero/negative qty rejected; discount <0 or >20 rejected; confirm with
   sufficient stock → status + stock deducted; confirm with one insufficient
   item → no changes at all; repeated confirm → no extra deduction; cancel
   Confirmed → stock restored once; sales user accessing another user's
   order → 403; CSV with one invalid row → zero products imported."

## How generated code was reviewed

- I read every file before committing it.
- I tested each feature manually in the browser as both the admin and the
  sales role.
- The automated suite (152 tests) runs against a separate test database that
  is rebuilt from `schema.sql` and `seed.sql` at the start of every run.

## Corrections made

The first generated test fixtures connected to the development database
named in `.env`. Tests created and deleted rows there, and ten order tests
started failing as soon as a real order changed the seeded stock levels. I
specified a dedicated test database instead, and the fixtures were rewritten
to rebuild `sales_inventory_test` from `schema.sql` and `seed.sql` on each
run and to refuse to start if the test database name equals the real one.
Development data is no longer touched by the tests.
