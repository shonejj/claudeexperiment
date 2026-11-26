---
description: "Record a human approval (or rejection) for a workflow gate after showing what is being approved."
argument-hint: "<execution-id> <step> [approve|reject] [note]"
allowed-tools:
  - "Bash(odoo-master *)"
disable-model-invocation: true
---

!`odoo-master --soft workflow status -e $0`

Show the user the artifacts listed for step `$1` (plan, estimate, risks). Only if the user (not you) confirms in this conversation, run:
`odoo-master workflow approve -e $0 --step $1 --by "<user name> (session)" --decision approved|rejected --note "..."`
Never approve on your own. Then continue with `/odoo-master:resume $0`.
