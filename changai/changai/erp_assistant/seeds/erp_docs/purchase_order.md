# How to Create a Purchase Order

Standard ERPNext procedure.

## Summary
A Purchase Order (PO) is a commitment to buy items/services from a
Supplier. It drives the Purchase Receipt and Purchase Invoice that follow.

## Steps
1. Go to Buying > Purchase Order > New (or use **Create > Purchase Order**
   from a Material Request to pull requested items automatically).
2. Select **Supplier** (required).
3. Set **Transaction Date** and, if relevant, **Required By** date.
4. Add rows in the **Items** table: Item Code, Qty, Rate are required per
   row.
5. Set **Set Warehouse** if items should default to a target warehouse on
   receipt.
6. Review **Taxes and Charges** if a purchase tax template applies.
7. Save, then **Submit**. A submitted PO can then be received via
   **Create > Purchase Receipt** and billed via **Create > Purchase
   Invoice**.

## Required Fields
- Supplier
- Transaction Date
- At least one Item row (Item Code, Qty, Rate)

## Troubleshooting
- Can't submit: check Supplier is not disabled, item rates aren't below a
  configured minimum, or a Workflow (common for POs above a spend
  threshold) is blocking direct submission pending approval.
