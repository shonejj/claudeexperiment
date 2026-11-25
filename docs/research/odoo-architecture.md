# Odoo architecture (research notes)

Sources: odoo/documentation `content/developer/tutorials/server_framework_101/*`,
`content/developer/reference/backend/{orm,module,http,security}.rst`,
`content/developer/reference/frontend/framework_overview.rst` (branches 16.0–master), and the Odoo
source in the official Docker images 17.0–20.0.

## Three tiers
- **Data tier:** PostgreSQL. All business data is stored here. Binary attachments go in the
  *filestore* (`<data_dir>/filestore/<dbname>/`), not the database, unless
  `ir_attachment.location=db`.
- **Logic tier:** Python server (`odoo-bin`). Two server modes: threaded (default, `workers=0`), and
  prefork multi-process (`workers>0`) with a separate gevent worker on `--gevent-port` for
  `/websocket` (live chat, bus notifications). Source: `administration/on_premise/deploy.rst`.
- **Presentation tier:** the web client, a single-page app built on the OWL framework, plus the
  website/portal, which is server-rendered QWeb with interactive JS.

## Modules (addons)
An addon is a Python package with `__manifest__.py`. It is found through `--addons-path`.
Conventional layout (`module.rst`, tutorials):

```
my_module/
├── __init__.py            # imports models, controllers, wizard, (hooks)
├── __manifest__.py
├── models/                # Python models
├── views/                 # XML views, actions, menus
├── security/              # ir.model.access.csv (≤19) or ir.access.csv (20+), groups, rules
├── data/                  # XML/CSV data (often noupdate)
├── demo/
├── wizard/                # TransientModel wizards
├── report/                # QWeb reports + paperformat
├── controllers/           # http.Controller routes
├── static/src/{js,xml,scss}  # OWL components, assets
├── static/tests/          # JS tests, tours
├── tests/                 # Python tests (imported in tests/__init__.py)
├── i18n/                  # .pot / .po
└── migrations/<ver>/ or upgrades/<ver>/   # pre-/post-/end- upgrade scripts
```

## Registry and inheritance
- Each database has a **registry** that maps model names to classes, composed from every installed
  module's class in dependency order. This is why the `depends` order in the manifest matters: an
  extension only applies if the module that defines the model is a dependency.
- Three kinds of inheritance (`orm.rst` "Inheritance and extension"):
  1. **Classical / extension** — `_inherit = 'res.partner'` with no `_name`. Modifies the existing
     model in place (same table).
  2. **Prototype** — `_name = 'x'` + `_inherit = 'y'`. Creates a new model that copies y's fields
     (new table).
  3. **Delegation** — `_inherits = {'res.partner': 'partner_id'}`. Composition: fields of the parent
     are readable on the child through a required Many2one.
- Views are inherited with `inherit_id` + XPath (`position`: `inside`, `after`, `before`, `replace`,
  `attributes`, `move`). Templates (QWeb) the same way.
- JavaScript is extended with `patch()` (`frontend/patching_code.rst`) and registries
  (`frontend/registries.rst`).

## Extension points the agents must look for before writing code
(Odoo reuse ladder — see `instructions/odoo-development.md`)
1. Configuration or standard features (settings, automated actions, server actions, Studio-like
   options) — no code.
2. Data records: new `ir.actions.server`, `ir.cron`, `mail.template`, `ir.ui.menu`.
3. Model extension with `_inherit` (add fields, override compute/onchange/create/write, **always
   call `super()`**).
4. View extension with `inherit_id` + XPath — never copy the whole base view.
5. Hook methods that standard modules expose for overriding (e.g. `_prepare_invoice_values`,
   `_prepare_procurement_values`, `_get_*`). The project analyst greps the standard addon source
   for `def _prepare_` / `def _get_` on the model before proposing overrides.
6. New model / new module — only when 1–5 do not fit.
7. **Never** edit standard Odoo or Enterprise source (user requirement; enforced by the guard hook
   for paths detected as core addons).

## Request lifecycle (HTTP)
`http.Controller` routes declare `type='http'` or `'json'` (`'jsonrpc'` from 19.0) and
`auth='user'|'public'|'none'|'bearer'` (bearer appears in 18 docs for API keys). Every request opens
a cursor, builds an `env` (`request.env`), and commits at the end unless an exception occurs.
External API: XML-RPC/JSON-RPC (`external_api.rst`). JSON-2 API (`external_api` in 19+ docs)
uses API keys.

## Multi-company
Records carry `company_id`. `_check_company_auto = True` with `check_company=True` on relational
fields enforces consistency. Record rules (`ir.rule`, ≤19) or `ir.access` domains (20) restrict
company visibility with `company_ids` in the domain context.
