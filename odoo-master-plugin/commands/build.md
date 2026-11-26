---
description: "Implement a feature or change end-to-end through the matching workflow (intake, plan, approval, implementation, tests, review, evidence, report)."
argument-hint: "<request>"
allowed-tools:
  - "Bash(odoo-master *)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/bin/odoo-master *)"
  - "Bash(git status*)"
  - "Bash(git diff*)"
disable-model-invocation: true
---


Use the `project-intake` skill for: $ARGUMENTS
Start the workflow it selects and drive it with the `workflow-execution` skill. Respect every approval gate.
