---
description: "Check the environment for Odoo Master: Python deps, Docker + images, Node/Playwright, psql, LSP server, Claude Code version, state directory."
allowed-tools:
  - "Bash(odoo-master *)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/bin/odoo-master *)"
disable-model-invocation: true
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

!`${CLAUDE_PLUGIN_ROOT}/bin/odoo-master --soft doctor --brief --quick`

Explain which capabilities are fully available, degraded or unavailable (e.g. no Docker → runtime level cannot be verified), and the exact fix for each warning.
