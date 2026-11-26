---
description: "Fix a bug in an existing Odoo customisation: reproduce, root cause with evidence, regression test, fix, verify, review."
argument-hint: "<symptom, error or traceback>"
allowed-tools:
  - "Bash(odoo-master *)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/bin/odoo-master *)"
disable-model-invocation: true
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

Start the bug-fix workflow: `odoo-master workflow start bug-fix -i request="$ARGUMENTS"` and drive it with the `workflow-execution` skill (systematic debugging: no fix without a reproduced root cause).
