# What is a BOM, and How to Create One

Standard ERPNext procedure.

## Definition
A Bill of Materials (BOM) defines the raw materials, operations, and
quantities required to manufacture one unit of a finished/sub-assembly
Item. Work Orders and Job Cards are generated from a BOM.

## Steps to Create
1. Go to Manufacturing > BOM > New.
2. Select the **Item** this BOM produces (must be a manufacturable Item).
3. Set **Quantity** — the batch size this BOM describes (default 1).
4. Add rows under **Raw Materials**: Item Code and Qty per row are
   required; rate defaults from the Item's valuation/price.
5. If this is a multi-step manufacturing process, add rows under
   **Operations** (Operation, Workstation, Time in mins) — this requires
   Manufacturing Settings to have Operations enabled.
6. Set **Is Active** and **Is Default** if this should be the BOM used by
   default when creating Work Orders for the Item.
7. Save, then **Submit**.

## Required Fields
- Item (the item produced)
- At least one Raw Material row (Item Code, Qty)

## Troubleshooting
- Can't submit: a raw material Item may be disabled, or quantities may be
  zero/blank on a row.
