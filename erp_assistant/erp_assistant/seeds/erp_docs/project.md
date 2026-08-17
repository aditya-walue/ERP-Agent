# How to Create a Project

Standard ERPNext procedure.

## Summary
A Project groups Tasks, Timesheets, and costs under one deliverable. Create
one whenever you need to track work, time, or expenses against a client
engagement or internal initiative.

## Steps
1. Go to Projects > Project > New.
2. Enter **Project Name** (required).
3. Set **Status** (Open by default).
4. Optionally set **Expected Start Date** and **Expected End Date**.
5. Set **Priority** (Low/Medium/High) if used for scheduling.
6. Link a **Customer** if this project is billed to a client.
7. Set **Project Type** (Internal / External / Other) if configured.
8. Under the Costing tab, optionally set **Estimated Costing** and enable
   **Track Actual Costs from Timesheets** / **Track Sales Orders** if you
   want Timesheets/Sales Orders to roll up into project cost automatically.
9. Save.
10. Add **Tasks** from the Project's Tasks tab, or create Task records with
    this Project set as their parent.

## Required Fields
- Project Name

## Permissions
Default roles with Create permission on Project: Projects Manager,
Projects User, System Manager (varies by site configuration — check
DocType Permissions if unsure).

## Troubleshooting
- Project not saving: check for a required custom field left blank, or a
  Workflow that blocks direct creation (some implementations route new
  Projects through an approval workflow instead of allowing direct save).
