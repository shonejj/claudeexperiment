# Odoo development rules

## The Odoo reuse ladder (decide in this order, record the rung)
1. **Does standard Odoo already do it?** (configuration, settings, existing app features, automation rules,
   server actions). Check `knowledge/standard-modules/models-<series>.json` and the standard module source in
   the official image before writing code.
2. **Is there an existing custom module for this business area?** Extend it (inventory: `project-inventory.json`).
3. **Data only?** Records in XML/CSV (mail templates, crons, actions, menus, sequences, server actions).
4. **Inheritance** — `_inherit` models, `inherit_id` + XPath views, `patch()` for JS, template inheritance.
   Override standard hook methods (`_prepare_*`, `_get_*`, `_action_*`) before public methods.
5. **New module** — only when 1–4 do not fit; bridge modules `<a>_<b>` for cross-app glue.
Never edit Odoo core or Enterprise files. Never copy a standard view or method body to change it.

## Code
- Manifest version `<series>.x.y.z`; bump on schema/data changes; license declared.
- Models: `_description` on new models; `@api.depends` complete; computes assign every record; overrides call
  `super()`; `@api.model_create_multi` for `create`; no queries in loops; `sudo()` narrow and justified.
- Constraints: `_sql_constraints` (≤18) / `models.Constraint`/`models.Index` (19+; `_sql_constraints` is ignored).
- Views: inherit with stable XPath anchors; expressions instead of `attrs` (17+); `<list>` (18+).
- Security: ACL for every new model and group (ir.model.access ≤19 / ir.access 20); record rules for
  multi-company/ownership; field `groups=` for sensitive fields.
- SQL: parameters / `odoo.tools.SQL`; `flush_model()` / `invalidate_model()` around raw SQL.
- i18n: user-facing strings translatable (`_()` / `self.env._()` on 18+); no f-strings inside `_()`.
- Tests: `tests/test_*.py`, tagged appropriately, data created in the test, run as non-superuser where access matters.
- Logging: `_logger = logging.getLogger(__name__)`; no `print`.

## Version table
See `${CLAUDE_PLUGIN_ROOT}/docs/research/odoo-version-compatibility.md` and `knowledge/odoo-versions.yaml`.
