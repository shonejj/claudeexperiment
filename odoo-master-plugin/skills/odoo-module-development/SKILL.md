---
name: odoo-module-development
description: "Creating or restructuring Odoo modules correctly for the target version: manifest keys and versioning, directory layout, data file order, dependencies, assets, hooks, i18n, and the decision whether a new module is justified at all. Use when scaffolding a module or changing manifests."
---

# Odoo module development

## Is a new module justified?
Only after the reuse ladder (instructions/odoo-development.md) says so. Prefer extending an existing custom module that owns the same business area; create a *bridge* module (`<a>_<b>`) when the change couples two independent apps.

## Scaffold (version-aware)
`odoo-bin scaffold` exists in every series, but write files explicitly so they match the detected version:
```
<module>/
  __init__.py            # from . import models[, controllers, wizard]
  __manifest__.py
  models/__init__.py
  security/ir.model.access.csv      # ≤19.0
  security/ir.access.csv            # 20.0+
  views/<model>_views.xml
  tests/__init__.py, tests/test_<feature>.py
```
## Manifest
```python
{
    "name": "Stock Quality Check",
    "version": "18.0.1.0.0",          # <series>.<x.y.z>; bump when data/schema changes
    "summary": "...",
    "license": "LGPL-3",              # GPL-2/3(+), AGPL-3, LGPL-3, OEEL-1, OPL-1, Other proprietary...
    "depends": ["stock"],             # minimal; transitive deps are fine for refs
    "data": [                          # order matters: groups → ACL → data → views → menus
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/quality_check_views.xml",
        "views/menus.xml",
    ],
    "assets": {"web.assets_backend": ["stock_quality_check/static/src/**/*"]},
    "installable": True,
    "application": False,
}
```
- Hooks: `post_init_hook = "post_init_hook"` with `def post_init_hook(env):` (17+), `(cr, registry)` on 16.
- Demo data is no longer loaded by default from 19.0; tests must create their own data.
- External deps: `"external_dependencies": {"python": ["requests"]}`.
- Validate: `odoo-master validate --modules <module> --brief`, then `odoo-master runtime test --modules <module>`.
