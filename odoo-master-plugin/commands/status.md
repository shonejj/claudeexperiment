---
description: "Show the Odoo Master dashboard: version, active workflow executions, pending approvals, MCP integrations, runtime instances, recent webhook events."
allowed-tools:
  - "Bash(odoo-master *)"
disable-model-invocation: true
---

!`odoo-master --soft status --brief`

Present this dashboard. For every pending approval, tell the user what is waiting and offer `/odoo-master:approve <execution> <step>`. For active executions offer `/odoo-master:resume <execution>`.
