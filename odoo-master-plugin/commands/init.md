---
description: "Initialise Odoo Master in this project: config file, optional event routes, optional recommended permissions in .claude/settings.json (backup first)."
argument-hint: "[--events] [--settings]"
allowed-tools:
  - "Bash(odoo-master *)"
disable-model-invocation: true
---

Explain what will be created, then run `odoo-master init $ARGUMENTS`.
`--settings` merges recommended permission rules into `.claude/settings.json` additively and writes a `.bak` first — ask before using it. Afterwards run `odoo-master analyze --brief`.
