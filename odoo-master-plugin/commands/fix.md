---
description: "Fix a bug in an existing Odoo customisation: reproduce, root cause with evidence, regression test, fix, verify, review."
argument-hint: "<symptom, error or traceback>"
allowed-tools:
  - "Bash(odoo-master *)"
disable-model-invocation: true
---

Start the bug-fix workflow: `odoo-master workflow start bug-fix -i request="$ARGUMENTS"` and drive it with the `workflow-execution` skill (systematic debugging: no fix without a reproduced root cause).
