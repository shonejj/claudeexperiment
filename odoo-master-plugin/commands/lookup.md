---
description: "Where is a standard Odoo model or module defined, what extends it, and what does the standard source look like (official image, no clone)."
argument-hint: "<model|module> <name> [--series 18.0]"
allowed-tools:
  - "Bash(odoo-master *)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/bin/odoo-master *)"
disable-model-invocation: true
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

!`${CLAUDE_PLUGIN_ROOT}/bin/odoo-master --soft lookup $ARGUMENTS`

To find extension points or view anchors, use `odoo-master source grep "<regex>" --module <module> [--series S]` and `odoo-master source show <path> --start N --end M --plain`. Cite odoo/addons/... paths with line numbers.
