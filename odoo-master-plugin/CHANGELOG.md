# Changelog

## 0.2.0 — 2026-11-26
Added
- 20 slash commands (`commands/`), output style `odoo-engineer`, a monitor (`odoo-master watch`), `.lsp.json` (pyright), `engines`, 4 new plugin options (enterprise path, postgres image, ticket approval label, report formats), bridged to the CLI.
- Hooks: SubagentStart (project context for plugin agents), SubagentStop (STATUS reporting contract), SessionEnd (session summary), PostToolUse Bash (automatic evidence capture).
- CLI: `scaffold` (version-correct modules 16.0–20.0), `source grep|show|upgrade-code` (official images), `lookup model|module`, `doctor`, `init [--events] [--settings]`, `status`, `watch`, global `--soft` / `--max-lines`.
- Recommended project permissions template, merged additively by `odoo-master init --settings`.
- Live session harness `tests/live/run_live_sessions.py` (6/6 passing); pytest suite now 94 tests; all 8 evals executed.
- `detect-version --confirm <series>`; module edits are held while version signals conflict; the prompt hook records a series the user names.
- Intent hints on prompts and a SessionStart toolbox line (validator, runtime, scaffold, estimator, source lookup).
- Stop gate: baseline snapshots (only newly introduced errors block) and a one-time validation-run request.
Fixed
- Skill `` !`...` `` injections used `||`/pipes and were refused in the default permission mode; they now run as single pre-approved commands.
- Runtime database passwords could start with `-` and break the image's `wait-for-psql.py` (random failures).
- `upgrade_code` ran through the image entrypoint, which waits for a database; it now bypasses it.
- `attrs` set through `<attribute name="attrs">` was not detected.
- `category_id` on `res.groups` is a hard install error on 19.0 (was a warning); the rule is now scoped to `res.groups` records.
- `status` showed no module count before a full analysis.
- The CLI was referenced by bare name although the plugin `bin/` is not on PATH everywhere (e.g. eval sandboxes); now absolute paths.
- Odoo 20 counts of non-target tests (web JS suites) no longer make a module without tests look tested.

## 0.1.0 — 2026-11-25
First release.
- Project intelligence: inventory, architecture and dependency maps, multi-signal Odoo version detection (16.0–20.0).
- Knowledge: 21 version rules checked against official Odoo sources; standard module dependency graphs and model→module maps for 16.0–20.0.
- Static validator (manifest, XML, references against transitive dependencies, security, Python, JS, version rules).
- Docker runtime test runner (install + upgrade with Odoo tests), log summariser, ephemeral instances for visual QA.
- Read-only PostgreSQL inspection with production refusal.
- Migration scan and plan.
- Workflow engine + 15 workflows; native Claude Code parallel review workflow.
- 25 agents, 33 skills, 8 hook handlers, 7 policies, 10 JSON schemas, templates.
- MCP capability registry with stdio/HTTP probing and session registration; bundled read-only MCP server.
- Signed webhook receiver for GitHub, Slack, Jira and Linear, with dedupe and routing.
- Markdown→HTML→PDF reports with verification; evidence manifests.
- 71 pytest tests; 8 `claude plugin eval` cases with Jira MCP mocks.
