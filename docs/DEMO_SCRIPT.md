# Demo walkthrough — approximately 6 minutes

Record the browser at a readable size and explain each step in your own words. Start with the seeded database and know both sample passwords. Avoid showing `.env` or passwords in the recording.

| Time | Demonstration and explanation |
| --- | --- |
| 0:00–0:40 | Introduce the trading-company problem and Flask, JavaScript and MySQL stack. Log in as Admin. |
| 0:40–1:20 | Open customers and products. Demonstrate search, status filters and adding a customer. Explain deactivation and protected deletion. |
| 1:20–2:20 | Create an order using Keyboard quantity 2 and Mouse quantity 3, with a 10% discount. Show live total 4050. Save the draft and show stock is unchanged. Explain that the server supplies prices and calculates final totals. |
| 2:20–3:15 | Confirm the order and show stock dropping by 2 and 3. Show the stock movement report. Cancel and show stock restoration. Explain repeated requests and the single transaction. |
| 3:15–4:00 | Create an order exceeding available stock and show confirmation rejection. Explain that the complete transaction rolls back. Make a reasoned stock adjustment. |
| 4:00–4:40 | Upload the invalid CSV and show row-level errors and no new products. Upload the valid CSV and show products and opening movements. |
| 4:40–5:20 | Confirm a valid order and show customer sales, product sales, low stock and date filtering. Explain that cancelled orders are excluded and customers without sales show zero. |
| 5:20–5:50 | Log out and sign in as Sales User. Show the restricted navigation and own-order list. Explain server-side ownership checks. |
| 5:50–6:30 | Show test results and Git history. Explain the debugging exercise and AI disclosure. Mention any remaining limitations recorded in verification notes. |

For the interview, practice explaining why browser totals cannot be trusted, how SELECT FOR UPDATE prevents overselling, why Decimal is used, and how the report avoids counting orders more than once.
