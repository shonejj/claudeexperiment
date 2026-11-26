---
description: "Set up or check event-driven automation (Jira/GitHub/Slack/Linear webhooks \u2192 workflows): routes, secrets, receiver, recorded executions."
argument-hint: "[setup|check|records]"
allowed-tools:
  - "Bash(odoo-master *)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/bin/odoo-master *)"
disable-model-invocation: true
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

Action: $ARGUMENTS (default: check)
- setup: `odoo-master init --events` → explain `.odoo-master/events/routes.yaml`, the secret env vars, how to expose `odoo-master events serve` behind TLS, and the provider-side webhook configuration (docs/jira-integration.md). Do not start a public listener yourself.
- check: `odoo-master events routes` and `odoo-master events executions`; explain what each record will run.
- records: list recent records and offer to start the recorded workflows interactively.
