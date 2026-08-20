# How to Add a New Notification

Standard ERPNext procedure.

## Summary
A Notification automatically sends an alert (system notification, email,
or SMS) when a document meets a condition — created, updated, or a value
changed. Use it for reminders, approvals, and status alerts without
writing code.

## Steps
1. Go to Settings > Notification > New (or search "Notification").
2. Set **Document Type** — the DocType this notification watches (e.g.
   Sales Invoice, Leave Application, Material Request).
3. Set **Event** — when it fires:
   - **New** — on document creation
   - **Save** — every time the document is saved
   - **Submit** / **Cancel**
   - **Days Before/After** — relative to a date field (e.g. 3 days before
     `due_date`) — requires setting **Date Changed** and **Days in
     Advance**.
   - **Value Change** — when a specific field changes; set **Value
     Changed** to that fieldname.
4. Optionally add a **Condition** (Python expression evaluated against
   `doc`), e.g. `doc.status == "Overdue"`.
5. Under **Recipients**, choose **Channel**: System Notification, Email,
   Slack, or SMS (availability depends on what's configured).
   - For System Notification / Email: set **Recipients** — a fixed list of
     users/emails, or a **Recipients by Document Field** (e.g. the
     document's `owner` or a custom "assigned_to" field).
6. Set **Subject** and **Message** — both support Jinja templating against
   the document, e.g. `{{ doc.name }}` or `{{ doc.customer }}`.
7. Save. The Notification is active immediately (toggle **Enabled** off to
   pause it without deleting).

## Required Fields
- Document Type
- Event
- Channel
- Recipients (or Recipients by Document Field)
- Subject, Message

## Troubleshooting
- Not firing: confirm **Enabled** is checked, the **Event** matches how
  the document is actually being changed (e.g. "Value Change" won't fire
  on a plain Save unless that field changed), and any **Condition**
  expression isn't silently evaluating to False.
- Not received: check the recipient field actually resolves to a valid
  user/email on the document, and that email sending is configured for
  Email channel.
