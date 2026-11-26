---
description: "Show the Odoo Master dashboard: version, active workflow executions, pending approvals, MCP integrations, runtime instances, recent webhook events."
allowed-tools:
  - "Bash(odoo-master *)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/bin/odoo-master *)"
disable-model-invocation: true
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

!`${CLAUDE_PLUGIN_ROOT}/bin/odoo-master --soft status --brief`

Present this dashboard. For every pending approval, tell the user what is waiting and offer `/odoo-master:approve <execution> <step>`. For active executions offer `/odoo-master:resume <execution>`.
