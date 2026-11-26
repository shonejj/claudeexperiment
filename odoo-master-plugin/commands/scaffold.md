---
description: "Create a new, version-correct Odoo module skeleton (model, views, security, menu, tests) for the detected or given series, then validate it."
argument-hint: "<module_name> [--model x.y] [--depends a,b] [--series 19.0]"
allowed-tools:
  - "Bash(odoo-master *)"
disable-model-invocation: true
---

Before scaffolding, check the reuse ladder (`${CLAUDE_PLUGIN_ROOT}/instructions/odoo-development.md`): is there an existing custom module for this business area (`odoo-master inventory --summary`)? If yes, recommend extending it and ask before creating a new module.

Then run: `odoo-master scaffold $ARGUMENTS`
Show the generated tree, explain the version-specific choices (list/tree, attrs vs expressions, `_sql_constraints` vs `models.Constraint`, `ir.model.access.csv` vs `ir.access.csv`, groups/privileges, hook signatures), and the validation result. Offer `/odoo-master:test <module>`.
