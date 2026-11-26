---
description: "Run Odoo static validation (manifest, XML/XPath, references, security, Python, JS, version rules) and explain/fix the findings."
argument-hint: "[module,module2] [--series 18.0]"
allowed-tools:
  - "Bash(odoo-master *)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/bin/odoo-master *)"
disable-model-invocation: true
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

!`${CLAUDE_PLUGIN_ROOT}/bin/odoo-master --soft --max-lines 80 validate --brief $ARGUMENTS`

Explain each error with its fix (cite file:line). Offer to fix them; when the user agrees, fix them and re-run `odoo-master validate --brief`. This is the **static** level only — say that runtime was not executed.
