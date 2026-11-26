---
description: "Install and upgrade modules in a disposable Odoo + PostgreSQL (Docker) and run their Odoo tests; report counts honestly."
argument-hint: "<module[,module2]> [--series 18.0]"
allowed-tools:
  - "Bash(odoo-master *)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/bin/odoo-master *)"
  - "Bash(docker *)"
disable-model-invocation: true
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

Run `odoo-master runtime test --modules $ARGUMENTS` (add `--series` if the user gave one; Docker required — check with `odoo-master runtime check`).
Report per pass (install, upgrade): status, tests run, failures, the first traceback (use `odoo-master logs summarize <log>`).
`passed_no_tests` is NOT a pass. If Docker is unavailable, say the runtime level was not executed.
Record evidence when an execution is active: `odoo-master evidence add -e <id> --kind runtime-test --level runtime --path <result json> --status <status>`.
