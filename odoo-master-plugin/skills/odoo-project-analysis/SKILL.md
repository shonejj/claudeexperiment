---
name: odoo-project-analysis
description: "Deep Odoo-specific analysis of a codebase: custom vs standard modules, inherited standard models, view inheritance chains, security definitions, dependency graph (cycles, unknown/Enterprise deps), tests, controllers, OWL components, and incomplete implementations. Use to understand an existing Odoo project or a feature area before designing changes."
allowed-tools: "Bash(odoo-master *)"
---

# Odoo project analysis

Facts: !`odoo-master --soft --max-lines 60 inventory --summary`

## Read the knowledge model
- `.odoo-master/project-inventory.json` → per module: manifest, models (fields, methods, `calls_super`), views (`inherit_id`), actions, menus, ACL rows, rules, groups, controllers (routes/auth), OWL component count, tests, migrations.
- `.odoo-master/architecture-map.json` → for each model: custom modules defining/extending it, `standard_defined_in` (from the official image of the detected series), views per module.
- `.odoo-master/module-dependency-map.json` → graph, reverse deps, install order, cycles, unknown and Enterprise dependencies.

## Feature-area analysis
1. Identify the business flow (e.g. receipts → `stock.picking` with `picking_type_code='incoming'`).
2. Collect custom touch points (fields/methods/views/rules) with `path:line`.
3. Identify the standard module that owns the flow (`knowledge/standard-modules/models-<ver>.json`) and its extension hooks. With Docker available, inspect real standard source without cloning:
   `docker run --rm --entrypoint grep odoo:<ver> -rn "def _prepare_picking" /usr/lib/python3/dist-packages/odoo/addons/stock/models/`
4. Detect incomplete implementations: fields never shown in views, views referencing missing fields, models without ACL, computes without `@api.depends`, overrides without `super()`, TODO/FIXME markers, modules without tests.
5. Separate **code-level** knowledge from **database-level** knowledge (installed modules, data volumes, actual schema) — the latter needs `odoo-database-analysis` with an authorised database.

Output: a context brief table — claim | evidence (`path:line` or `NOT FOUND`/`UNVERIFIED`).
