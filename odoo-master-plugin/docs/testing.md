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

## Verification record (0.2.0, 2026-11-26)
| What | Level | Result |
|---|---|---|
| `pytest` (94 tests: core, hooks via subprocess, MCP, webhooks incl. a real HTTP receiver, Linear, reports/PDF, evidence, planning, scaffold for 16–20, lookup/doctor/init/status/watch, component formats, LSP handshake, scenarios A/C/E/F) | unit + integration | 94 passed |
| `claude plugin validate --strict` (plugin and marketplace) | static | passed |
| Scaffolded module `om_asset_register` on official `odoo:16.0`, `17.0`, `18.0`, `19.0`, `20.0` (install + upgrade + its own tests) | runtime | **passed on all five** (2 tests each, 0 failures) |
| Migration chain 17.0 → 18.0 → 19.0 with `odoo-master source upgrade-code` + scan + validate + manual remainder | runtime | passed on 18.0 and 19.0; `upgrade_code` did not fix `groups_id` in tests or `category_id` on `res.groups` (caught by the plugin) |
| Odoo 18 fixture: install + upgrade + tests; Playwright login + 2 views × 2 widths | runtime, browser | passed (0 console errors, 0 failed requests) |
| Read-only DB inspection on a real Odoo 18 database; production refusal; write rejected by read-only transaction | database | passed |
| **Live Claude Code sessions** (`tests/live/run_live_sessions.py`, headless `claude -p --plugin-dir`): plugin/agents/skills/commands/MCP loading, guard denies `git push --force`, post-edit feedback makes Claude replace `attrs`, `/odoo-master:status`, SubagentStart/Stop + `STATUS` contract, `/odoo-master:scaffold` on 20.0 | integration (real sessions) | **6/6 passed** |
| Native workflow `/odoo-master:odoo-parallel-review` (headless, `Workflow` tool allowed) on a commit with planted bugs | integration | ran 3 parallel reviewers; found SQL injection, missing `super()`, singleton bug |
| `claude plugin eval` — all 8 cases, 1 run each | behavioural | 7 × 1.0; `no-core-edit` 0.5 (no core file written = pass; inheritance-explanation judge failed this run, passed in an earlier run) |
| Real Jira/Slack/GitHub servers | integration | not tested (no credentials); covered with MCP mocks and signed simulated webhooks |
| LSP diagnostics inside a session | integration | the `LSP` tool was present in eval sessions; diagnostics content not asserted |
| Monitors | integration | not testable headless (Claude Code does not start monitors with `-p`); `watch` logic unit-tested |
| Production deployment verification | production | never automated |

### Findings from live testing that changed the plugin
- Skill `` !`...` `` injections with `||`/pipes were refused in default permission mode → single pre-approved commands.
- The plugin `bin/` is not on PATH inside `claude plugin eval` sandboxes → every skill, command and agent uses `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master`; hooks print the absolute path.
- Random runtime failures: generated DB passwords starting with `-` broke `wait-for-psql.py` → hex passwords.
- Odoo 20 runs `web` JS suites even with `--test-tags /<module>` → only the target module's tests count.
- `category_id` on `res.groups` fails installs on 19.0 → error rule scoped to `res.groups`.
- `attrs` via `<attribute name="attrs">` was missed → rule extended.
- The Stop gate blocked on errors that existed before the session → baseline snapshots; only new errors block.
- Models skipped the validator/estimator unless told → SessionStart toolbox line, intent hints on prompts, one-time "run validation" nudge.
- Version conflicts were ignored → module edits are held until the series is confirmed (automatically when the user's prompt names it).

### Running the live checks yourself
```
python3 tests/live/run_live_sessions.py --out live.json         # ~$1.2 of API usage
claude plugin eval . --scaffold --runs 1                         # needs bubblewrap + socat for the sandbox
```

## Verification record (0.1.0, 2026-11-25, build environment)
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
