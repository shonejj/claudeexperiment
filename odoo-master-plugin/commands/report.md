---
description: "Render a Markdown plan/report to HTML and a verified PDF."
argument-hint: "<file.md> [--formats html,pdf]"
allowed-tools:
  - "Bash(odoo-master *)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/bin/odoo-master *)"
disable-model-invocation: true
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

Run `odoo-master report $ARGUMENTS` and report the output paths, the PDF engine used and the verification (page count). If the engine was reportlab, mention that styling is limited and how to install Playwright.
