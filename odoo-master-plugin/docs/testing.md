# Testing

## Verification levels
| Level | Meaning | Tool |
|---|---|---|
| static | no execution: manifest, XML, security, Python AST, JS syntax, version rules | `odoo-master validate` |
| unit | plugin/core unit tests, or non-Odoo unit tests | `pytest` |
| integration | components together (hooks via subprocess, MCP stdio probe, signed webhooks) | `pytest` |
| runtime | real Odoo + PostgreSQL in Docker: install, upgrade, Odoo tests | `odoo-master runtime test` |
| database | read-only checks on an authorised database | `odoo-master db` |
| browser | Playwright against a live instance | `scripts/visual/odoo_check.mjs` |
| production | verification on production | never automated; human runbook |
Reports always list the levels achieved and the levels missing.

## Running the plugin's own tests
```
cd odoo-master-plugin
python3 -m pytest -q                      # unit + integration (66 tests); includes `claude plugin validate` if claude is installed
claude plugin eval . --runs 1             # behavioural evals (spawns Claude runs; costs tokens)
```
Live runtime check against the fixture (needs Docker):
```
bin/odoo-master --root tests/fixtures/odoo18_project runtime test --modules stock_quality_check --addons tests/fixtures/odoo18_project/addons
```

## Fixtures
`tests/fixtures/` contains Odoo 16, 17, 18, 19 and 20 projects, a deliberately broken module, and signed-webhook payloads.

## Regenerating standard module maps (new Odoo series)
```
docker run --rm --entrypoint python3 odoo:<series> -c '<extraction script>' > knowledge/standard-modules/community-<series>.json
```
The extraction scripts walk `/usr/lib/python3/dist-packages/odoo/addons/*/__manifest__.py` (depends) and every
model class (`_name`/`_inherit`). The same logic is in the commit that added these files.
