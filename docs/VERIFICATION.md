# Verification record

Verified on 7 November 2026 using Windows, Python 3.11 and MySQL Community Server 8.4.13.

## Automated verification

The final suite passed all 32 tests against a dedicated MySQL database in 108.59 seconds. This includes financial totals and discounts, rejection of invalid and oversized quantities, inactive and duplicate products, price snapshots, draft and final-state rules, all-or-nothing stock rollback, repeated confirmation and cancellation, ownership and admin permissions, CSRF checks, valid and invalid CSV import, stock adjustment validation, zero-customer reporting, protected deletion and the corrected debugging exercise.

Three tests exercise actual MySQL concurrency. Two orders competing for limited stock result in one successful confirmation and one rejection. Simultaneous repeated confirmation deducts stock once. Simultaneous repeated cancellation restores stock once.

The standalone `sql/schema.sql` was executed successfully in the disposable MySQL test database. All five queries in `sql/reports.sql` also executed successfully. The verification tables were removed afterward.

JavaScript passed Node's syntax check. Python source was formatted with Black and HTML, CSS and JavaScript with Prettier.

## Browser verification

A real Microsoft Edge browser completed login, product selection, dynamic item rows, live totals, draft saving, confirmation, cancellation, reports and product screens without JavaScript errors. The order editor and product screen were visually inspected. The live demo further exercises customer creation, failed confirmation, reasoned adjustment, invalid and valid CSV imports, reports and the Sales User view.

## Scope and limitations

The app runs locally using Flask's development server. Public deployment is optional in the assignment and is not configured. Currency is INR, with one stock location. The project uses a neutral Git author identity because the candidate's full name and preferred commit email were not provided. The submission archive name contains the FullName placeholder and must be renamed before submission.

The demonstration is an automatically recorded, captioned browser walkthrough without voice narration. Demo activity remains in the local application database. The included seed command creates a clean sample dataset in a new database on another machine. Private local credentials, virtual environments and MySQL runtime files are excluded from the submission package.
