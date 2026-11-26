---
description: "Resume a workflow execution after a pause, approval, compaction or new session."
argument-hint: "[execution-id]"
allowed-tools:
  - "Bash(odoo-master *)"
disable-model-invocation: true
---

!`odoo-master --soft --max-lines 30 workflow executions`

Pick execution `$ARGUMENTS` (or ask if several are active), run `odoo-master workflow status -e <id>` then `odoo-master workflow next -e <id>`, and continue with the `workflow-execution` skill.
