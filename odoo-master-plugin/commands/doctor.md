---
description: "Check the environment for Odoo Master: Python deps, Docker + images, Node/Playwright, psql, LSP server, Claude Code version, state directory."
allowed-tools:
  - "Bash(odoo-master *)"
disable-model-invocation: true
---

!`odoo-master --soft doctor --brief --quick`

Explain which capabilities are fully available, degraded or unavailable (e.g. no Docker → runtime level cannot be verified), and the exact fix for each warning.
