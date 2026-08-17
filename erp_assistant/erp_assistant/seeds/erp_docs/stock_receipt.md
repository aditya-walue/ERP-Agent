# How to Receive Stock

Standard ERPNext procedure. Two common paths depending on whether the
receipt is against a Purchase Order or a standalone stock movement.

## Path A — Receiving against a Purchase Order (most common)
1. Open the submitted **Purchase Order**.
2. Click **Create > Purchase Receipt**. Items, quantities, and warehouse
   default in from the PO.
3. Adjust **Received Qty** per row if the delivery is partial or over/under.
4. Confirm **Accepted Warehouse** (and **Rejected Warehouse** if quality
   inspection rejects some quantity).
5. Save, then **Submit** — this increases stock (Stock Ledger Entry) in the
   target warehouse and, if the Purchase Order isn't fully billed yet,
   leaves it open for a later Purchase Invoice.

## Path B — Standalone stock receipt (no Purchase Order)
1. Go to Stock > Stock Entry > New.
2. Set **Stock Entry Type** to "Material Receipt".
3. Add Item rows with **Qty** and the **Target Warehouse**.
4. Save, then **Submit**.

## Required Fields
- Item, Qty, and a target Warehouse per row (Path A also requires a
  submitted Purchase Order to receive against).

## Troubleshooting
- Stock not increasing: confirm the document was **Submitted**, not just
  saved as a draft — draft documents don't post Stock Ledger Entries.
- Wrong warehouse: check **Set Warehouse** on the PO / Stock Entry Type
  default warehouse configuration.
