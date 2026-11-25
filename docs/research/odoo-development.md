# Odoo development reference (research notes)

Sources: odoo/documentation `content/developer/reference/backend/{module,orm,data,security,testing,
actions,reports,http,mixins,performance}.rst` and `frontend/*.rst`; source in images 17.0–20.0.
For version differences see `odoo-version-compatibility.md`.

## Manifest (`module.rst`, master)
Keys: `name` (required), `version`, `description`, `author`, `website`, `license` (default `LGPL-3`;
allowed `GPL-2`, `GPL-2 or any later version`, `GPL-3`, `GPL-3 or any later version`, `AGPL-3`,
`LGPL-3`, `Other OSI approved licence`, `OEEL-1`, `OPL-1`, `Other proprietary`), `category`,
`depends`, `data`, `demo`, `test_data` (new after 16), `auto_install` (bool or list), `external_dependencies`
(`{'python': [...], 'bin': [...]}`), `application`, `assets`, `installable`, `maintainer`,
`sequence` (new after 16), `active` (deprecated), `pre_init_hook`/`post_init_hook`/`uninstall_hook`
(function names; signature `(env)` from 17, `(cr)`/`(cr, registry)` in 16).
Version convention: `<odoo major>.<module x.y.z>`, e.g. `18.0.1.0.0`. Migration directories use the
full version.

Validator rules (implemented in `scripts/odoo/validate_manifest.py`):
- file parses as a Python literal dict (`ast.literal_eval`), contains `name`;
- `license` in the allowed list; warn if missing (defaults to LGPL-3);
- every path in `data`/`demo` exists; security CSVs before the views that use the groups (warning);
- `depends` resolvable in the inventory (custom) or a known standard module name, otherwise "unknown
  — needs the addons path";
- version prefix matches the detected series.

## ORM essentials
- Model types: `models.Model` (persistent), `models.TransientModel` (wizards, auto-vacuumed),
  `models.AbstractModel` (mixins, no table).
- Fields: `Char, Text, Html, Integer, Float, Monetary, Boolean, Date, Datetime, Binary, Image,
  Selection, Many2one, One2many, Many2many, Reference, Many2oneReference, Json, Properties`.
  Common parameters: `string, required, readonly, index (True|'btree'|'btree_not_null'|'trigram'),
  default, compute, inverse, search, store, related, depends, compute_sudo, copy, groups,
  company_dependent, tracking (mail.thread), translate, ondelete (Many2one)`.
  `group_operator` was renamed `aggregator` (SaaS 17.2 → 18.0).
- Decorators: `@api.depends`, `@api.depends_context`, `@api.constrains`, `@api.onchange`,
  `@api.model`, `@api.model_create_multi` (override `create(self, vals_list)`), `@api.ondelete(at_uninstall=False)`,
  `@api.autovacuum`, `@api.private` (18.2+, not exposed over RPC).
- Recordset rules: iterate in compute methods (`for rec in self`), assign every record in a compute,
  avoid `search` in loops (prefetch), use `read_group`/`_read_group` for aggregates, use `sudo()`
  sparingly and never on user-supplied domains.
- SQL: use `self.env.cr.execute(SQL(...))` with the `odoo.tools.SQL` wrapper (17+) to avoid
  injection; call `flush_model()`/`invalidate_model()` around raw SQL (15.4+ API).

## Data files (`data.rst`)
`<odoo><record model="" id="">`, `<field name="" ref="" eval="">`, `<function>`, `<delete>`,
`<menuitem>`, `<template>`; `noupdate="1"` blocks protect user-edited data from being reset on
upgrade. CSV files are named after the model (`ir.model.access.csv`, `res.country.state.csv`).
External IDs are `module.xml_id`; references to records of other modules must be fully qualified and
the module must be in `depends`.

## Security (`security.rst`)
- Groups `res.groups` (`implied_ids`, `category_id` ≤18; `privilege_id` 19+).
- ACL CSV ≤19: `id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink`.
  `model_id:id` is `model_<model_with_underscores>`. **Every new persistent model needs at least
  one ACL row**, otherwise Odoo logs "has no access rules" and non-admin users cannot use it.
- Record rules ≤19: `ir.rule` with `domain_force`, `groups`, `perm_*`. Global rules (no group) are
  ANDed; group rules are ORed.
- 20.0: single `ir.access` model; CSV `id,name,model_id,group_id/id,operation,domain`, where
  `operation` is a subset of `crud` and `domain` gives restrictions.
- Field-level `groups=`, method-level `check_access(...)` (18+), and `sudo()` pitfalls. Never use
  `eval` on user input; use `ast.literal_eval` or `safe_eval` (`security.rst`). Escape in QWeb
  (`t-out`, not `t-raw`, which was removed in 15+).

## Views (`user_interface/view_architectures.rst`, `view_records.rst`)
form, list (`tree` ≤17), kanban, search, calendar, pivot, graph, activity, gantt/map/cohort
(Enterprise). Dynamic attributes from 17: `invisible="state != 'draft'"`, `readonly="..."`,
`required="..."`, column_invisible on list columns. Do not use `attrs`/`states` (rejected at load).

## Frontend (`frontend/*.rst`)
ES modules with `/** @odoo-module **/` (implicit from 17 for files in `static/src`), OWL
components, `registry.category("fields"|"views"|"actions"|"services"|...)`, `patch()`, services
(`orm`, `action`, `notification`, `rpc`), asset bundles (`web.assets_backend`, `web.assets_frontend`,
`web.assets_tests`, `web.assets_unit_tests` (18+, Hoot)). JS unit tests: QUnit (≤17), Hoot (18+).
OWL 3 from 20.0.

## Reports (`reports.rst`)
`ir.actions.report` (`report_type="qweb-pdf"`), QWeb template calling `web.external_layout`,
wkhtmltopdf for PDF rendering (0.12.6 recommended in `source.rst`).

## Testing (`testing.rst`)
`odoo.tests.TransactionCase` (rolled back per test; `setUpClass` data shared), `SingleTransactionCase`,
`HttpCase` (`url_open`, `browser_js`, `start_tour`), `Form` helper for onchange simulation,
`@tagged('post_install', '-at_install')`. Run with
`odoo-bin -d <db> -i <mod> --test-tags /<mod> --stop-after-init` (or `-u` for upgrades).
`--test-tags` spec: `[-][tag][/module][:class][.method]`. Tours: `registry.category("web_tour.tours")`
in `static/tests/tours/`, launched from a Python `HttpCase`. Odoo 20 adds `--with-test-data` shared
companies/users.

## Performance (`performance.rst`)
Profiling with `--dev` and the profiler (`odoo.tools.profiler.Profiler`), indexes on searched
fields, `search_fetch` (16.2+), avoid N+1 by batching and prefetch, `compute_sql` (SaaS 19.1+).
