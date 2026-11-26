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
python3 -m pytest -q                      # unit + integration + scenario tests (71); includes `claude plugin validate` if claude is installed
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

## Verification record (2026-11-25, build environment)
| What | Level | Result |
|---|---|---|
| `pytest` suite (71 tests: version, inventory, validator, migration, workflow engine, hooks via subprocess, MCP probe/registry, webhooks, reports/PDF, evidence, planning, plugin structure, end-to-end CLI scenarios A/C/E/F) | unit + integration | 71 passed |
| `claude plugin validate` (plugin and marketplace) | static | passed |
| `stock_quality_check` fixture on `odoo:18.0` + `postgres:16`: install and upgrade with `--test-tags` | runtime | passed, 2 tests, 0 failures |
| Odoo 17 / 19 / 20 fixtures on `odoo:17.0` / `19.0` / `20.0` | runtime | install and upgrade clean; `passed_no_tests` (fixtures have no tests; correctly not counted as a pass) |
| Playwright login + 2 views × 2 widths on a disposable Odoo 18 | browser | ok: 0 console errors, 0 failed requests |
| `odoo-master db overview/model` on a real Odoo 18 database; production DSN refused; write rejected by the read-only transaction | database | passed |
| Report → PDF via Playwright Chromium, verified with pypdf | integration | passed |
| `claude plugin eval` `existing-repo-analysis` (1 run) | behavioural | 3/3 graders |
| `claude plugin eval` `plan-comment-posted` with mocked Atlassian MCP (1 run) | behavioural | 4/4 graders (searched, read INV-42, commented only on INV-42) |
| Other 6 eval cases | behavioural | defined, not executed in this build (cost/time); run `claude plugin eval . --scaffold` |
| Production deployment verification | production | not applicable / never automated |
