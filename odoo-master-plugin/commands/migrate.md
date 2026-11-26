---
description: "Analyse and plan (then, after approval, perform) a migration of custom modules between Odoo versions, one hop at a time."
argument-hint: "<from> <to> [modules]"
allowed-tools:
  - "Bash(odoo-master *)"
disable-model-invocation: true
---

Arguments: source=$0 target=$1 modules=$2
!`odoo-master --soft --max-lines 60 migration scan --from $0 --to $1`

Summarise the blockers per hop (cite file:line and the rule source), the database implications and risks, then start the workflow:
`odoo-master workflow start odoo-migration -i source=$0 -i target=$1` (+ `-i modules=$2` if given) and drive it with the `workflow-execution` skill. The plan gate always needs a human.
