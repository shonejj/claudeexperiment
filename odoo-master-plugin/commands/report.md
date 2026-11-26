---
description: "Render a Markdown plan/report to HTML and a verified PDF."
argument-hint: "<file.md> [--formats html,pdf]"
allowed-tools:
  - "Bash(odoo-master *)"
disable-model-invocation: true
---

Run `odoo-master report $ARGUMENTS` and report the output paths, the PDF engine used and the verification (page count). If the engine was reportlab, mention that styling is limited and how to install Playwright.
