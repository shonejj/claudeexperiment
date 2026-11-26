---
description: "Plan a change without implementing it: requirements, reuse decision, technical design, module and database impact, estimate and risks; render a PDF; ask for approval."
argument-hint: "<what to build or change>"
allowed-tools:
  - "Bash(odoo-master *)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/bin/odoo-master *)"
disable-model-invocation: true
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

Request: $ARGUMENTS

Follow the `project-intake` skill but stop before implementation: run the planning steps of the matching workflow (requirements → reuse check → design → estimate), write the plan from `${CLAUDE_PLUGIN_ROOT}/templates/architecture/technical-plan.md` into `.odoo-master/plans/<slug>/plan.md`, build the estimate with `odoo-master estimate --input ... --out .odoo-master/estimates/<slug>`, render with `odoo-master report <plan.md> --formats html,pdf`, and ask the user to approve. Do not write module code.
