---
name: visual-qa
description: "Browser verification of Odoo UI changes with Playwright against an ephemeral test instance: login with generated test credentials, open menus/records, capture screenshots at multiple widths, collect console errors and failed network requests, and record evidence. Use when views, templates or JS change."
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

# Visual QA

1. Instance: `odoo-master runtime serve --modules <m> [--series S] --port 8069` → prints URL and a credentials file for the throwaway database (`.odoo-master/session/runtime-<id>.json`, git-ignored). Never use real user accounts or production URLs.
2. Check:
```
node "${CLAUDE_PLUGIN_ROOT}/scripts/visual/odoo_check.mjs" \
  --url http://localhost:8069 --credentials .odoo-master/session/runtime-<id>.json \
  --paths "/odoo/action-stock_quality_check.stock_quality_check_action,/odoo/inventory" \
  --widths 1440,768,390 --out .odoo-master/screenshots/<execution>
```
   (`/odoo/...` URLs on 17.2+; `/web#action=...` on older series.)
3. Read the JSON report: per page HTTP status, console errors, failed requests, screenshot paths. Look at the screenshots.
4. Record: `odoo-master evidence add -e <id> --kind browser-check --level browser --path <report.json> --status passed|failed`.
5. Stop: `odoo-master runtime stop --run-id <id>`.
If Playwright/Chromium or Docker is unavailable, record the browser level as missing.
