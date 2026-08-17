# How to Create a Sales Invoice

Standard ERPNext procedure.

## Summary
A Sales Invoice records a sale to a Customer and, once submitted, creates
the corresponding accounting (GL) entries. It can be created standalone or
against a Sales Order / Delivery Note.

## Steps
1. Go to Accounts > Sales Invoice > New (or open a Sales Order/Delivery
   Note and click **Create > Sales Invoice** to pull items automatically).
2. Select **Customer** (required).
3. Set **Posting Date** (defaults to today).
4. Add rows in the **Items** table: Item Code, Qty, Rate are required per
   row. Amount is calculated automatically.
5. Review **Taxes and Charges** — apply a Sales Taxes and Charges Template
   if one is configured, or add rows manually.
6. Check **Payment Terms** / due date if the customer has approved credit
   terms.
7. Save (creates a draft, docstatus = 0).
8. Review the totals, then **Submit** (docstatus = 1) — this posts the GL
   entries and, if stock items are involved with "Update Stock" enabled,
   reduces inventory.

## Required Fields
- Customer
- Posting Date
- At least one Item row (Item Code, Qty, Rate)

## Troubleshooting
- Can't submit: check for a mandatory field left blank, an unbalanced
  Cost Center/Account setup, or a Workflow requiring approval before
  submission is allowed. Also check `frozen accounts` / closed Fiscal
  Year settings if the posting date falls in a locked period.
