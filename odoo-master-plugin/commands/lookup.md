---
description: "Where is a standard Odoo model or module defined, what extends it, and what does the standard source look like (official image, no clone)."
argument-hint: "<model|module> <name> [--series 18.0]"
allowed-tools:
  - "Bash(odoo-master *)"
disable-model-invocation: true
---

!`odoo-master --soft lookup $ARGUMENTS`

To find extension points or view anchors, use `odoo-master source grep "<regex>" --module <module> [--series S]` and `odoo-master source show <path> --start N --end M --plain`. Cite odoo/addons/... paths with line numbers.
