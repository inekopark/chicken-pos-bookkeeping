# Product and implementation plan

## Final MVP boundary
A single Windows PC, one cashier at a time, stock tracked by movement, retail/wholesale sales, cash/bank/e-wallet/credit, supplier delivery and partial settlement, customer collection, expenses, shift close and remittance, and daily transaction reports. No tax or statutory reporting claim. Processing and full double-entry follow after these controls are stable.

## Roles and workflows
Cashier: open shift → cart sale/credit or collection → count cash → remit → close. Supervisor: products, purchases, stock and processing, with auditable reasons. Bookkeeper/admin: pricing, AP/AR, opening balances, reports, corrections, backup/restore. Owner: read-only dashboard. The prototype has no enforced login or roles yet.

Purchase: delivery creates inventory and payable; settlement reduces payable, never adds purchase expense. Sale: stock and inventory value decrease, revenue and payment/receivable increase. Expense: selected payment account decreases. Shift: opening + drawer events = expected cash; counted minus expected = variance; counted minus remitted = retained. Payment from bank or GCash never affects drawer cash.

## Data model
Products connect to purchase_items, sale_items and immutable inventory movements. Purchases connect to supplier_payments; sales to customer_payments. Each shift connects to sales, drawer events and expense transactions. Future tables: users/roles, processing_batches/inputs/outputs/waste, stock_counts, remittances, journal_entries/lines, audit_events, opening_balances. All money is integer centavos, quantity integer thousandths of base unit, and timestamps UTC. Each business event commits atomically.

## Costing
Initial stock ledger uses moving weighted average: a receipt adds its cost; a sale takes the proportional cost of quantity sold. Rounding remainder stays in inventory. Negative stock is rejected. For chicken conversion, consume a costed whole-chicken batch and add measured cut outputs and explicit waste in the same transaction. Configurable allocation: output weight or relative selling value; record the chosen method, inputs, output yields, loss and allocation basis for each batch. Do not make a silent balancing product.

## Accounting event map (planned journal layer)
| Event | Debit | Credit |
| --- | --- | --- |
| Delivery on credit | Inventory | AP |
| Supplier payment | AP | Cash/Bank/GCash |
| Sale | Cash/Bank/GCash/AR | Sales |
| Sale cost | COGS | Inventory |
| Customer collection | Cash/Bank/GCash | AR |
| Cash expense | Expense | Cash |
| Owner draw | Drawings | Cash/Bank |
| Processing | Cut inventory and explicit loss | Whole inventory |

## Screens
Operator: shift, searchable cart, payment, receipt, collection, close/remit. Supervisor: deliveries, stock, cutting and count. Admin: master data, AP/AR, cash reports, journal drilldown, cutover, audit, backup/restore. Prototype currently has only simple one-line forms.

## Framework
Tkinter ships with Python and avoids a local web server; SQLite provides ACID transactions on one PC. Use PyInstaller for a signed or clearly identified Windows build after the workflows are validated. Multi-device concurrent operation would require a different architecture.

## Milestones
1. Prototype core and basic forms (current).
2. Migrations, credentials/roles, cart UI, AP/AR, receipts, cash exception controls, audit log, automated backups and restore rehearsal.
3. Processing/cutting, yield/cost allocation, waste and stock counts.
4. Cutover and automatic journals, trial balance and financial reports.
5. Installer, supervised pilot and release checks.

## Verification and recovery
Tests must cover atomic rollback, duplicate receipt/ref rejection, negative stock, partial settlement bounds, cash/bank separation, closure protection, conversion cost preservation and journal balance. Before operational use, make automatic timestamped SQLite online backups to a separate folder/device; admin backup button; checksum and `PRAGMA integrity_check`; restore into a separate database and verify counts before switch. This prototype exposes a core backup method but has no automated backup scheduler or restore UI.

## Business settings to confirm
Cash float policy, approved price overrides, credit limits, refunds, exact product units/conversions, count tolerances, which byproducts are purchased or produced, LPG resale vs consumption, cut costing basis, remittance destination, opening balance cutover, tax registration, and required receipt format. Use conservative defaults and require admin configuration for unsettled rules.
