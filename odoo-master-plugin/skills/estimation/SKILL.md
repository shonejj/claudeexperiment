---
name: estimation
description: "Effort estimation for Odoo/software work grounded in repository analysis: work breakdown into typed tasks with complexity and unknowns, computed by odoo-master estimate into hours, days, ranges and testing/review overhead. Use when a plan needs an estimate or a ticket asks 'how long'."
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

# Estimation

1. Break the plan into tasks (`schemas/estimate.schema.json`): `id, title, module, kind (model|view|security|controller|owl|report|data|migration|integration|test|devops|analysis|docs|review), complexity (trivial|simple|moderate|complex|very_complex), unknowns, new_module, touches_standard_flow, data_migration`.
2. Base the complexity on facts: number of models/views touched (inventory), override depth of standard flows, data volumes, version jumps.
3. Run `odoo-master estimate --input .odoo-master/estimates/<slug>.input.json` → per-task hours with multipliers, testing/review/docs overhead, total hours, days (config hours_per_day), low/high range by confidence, agent workload split.
4. Present as **effort estimate**, not a delivery date; list assumptions and what would change it.
5. Store output next to the plan; include in ticket comments.
