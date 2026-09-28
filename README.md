# Chicken POS & Bookkeeping (early prototype)

A Python/SQLite desktop application in development for a small Philippine chicken retail and wholesale business. The goal is to trace stock, sales, supplier debt, customer credit, cash drawer movements, and eventually processed chicken yields and bookkeeping entries.

## Current state

**Prototype, not ready for live business records.** The current Tkinter console supports product, supplier and customer creation; cashier shift opening/closing; one-product sales; one-product deliveries; expenses; and cash reconciliation. The core supports multi-line purchases and sales, partial supplier/customer payments, weighted average inventory cost, and SQLite transactions. Cashier login, permission enforcement, a complete processing workflow, refunds/reversals, journals, taxes, receipt printing, and recovery UI are still pending.

## Run on Windows

Install Python 3.12+ with Tkinter, then in PowerShell:

```powershell
cd chicken_pos
python app.py
```

The prototype database is created at `%USERPROFILE%\ChickenPOS\shop.sqlite3`. For a test run, use sample products and fictional transactions only.

## Tests

```powershell
cd chicken_pos
python -m unittest discover -s tests -v
```

## Architecture

- `core.py`: transactional business operations and SQLite schema.
- `app.py`: small Tkinter operator console.
- `tests/`: representative purchasing, sale, credit, cash, and rollback checks.
- `DESIGN.md`: MVP scope, flows, future data model, accounting map, milestones, and backup plan.

## Portfolio description

*Building a local-first POS and bookkeeping prototype for a chicken retailer: transactional inventory ledger, weighted average costing, supplier and customer balances, and cashier shift reconciliation in Python, SQLite, and Tkinter.*

## Next milestone

Add migrations, login and roles, split payments and multi-item cart UI, AP/AR screens, receipts, audit events, backup/restore interface, and reversible corrections before live use. See `DESIGN.md`.

No real customer or supplier information is included. Tax and BIR features are intentionally unimplemented pending verified requirements.
