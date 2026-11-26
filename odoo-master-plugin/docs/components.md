# Plugin components and file formats

Every file type in the plugin, its syntax, who consumes it, and what validates it.

| Path | Format | Consumer | Validated by |
|---|---|---|---|
| `../.claude-plugin/marketplace.json` | JSON: `name`, `owner`, `plugins[]{name, source, description}` | `/plugin marketplace add` | `claude plugin validate <repo>` |
| `.claude-plugin/plugin.json` | JSON manifest: name, version, description, author, license, keywords, `engines` (`claude-code >=2.1.300`), `workflows` (points at `claude-workflows/`), `userConfig` (7 options) | Claude Code | `claude plugin validate --strict`; `test_v2_features` (option types, option keys ↔ config bridge) |
| `agents/*.md` (25) | Markdown + YAML frontmatter: `name`, `description`, `tools`, `model`, `color`, `skills` | Agent tool (`odoo-master:<name>`) | `test_structure` (frontmatter, skills exist), live loading test |
| `skills/*/SKILL.md` (33) | Markdown + frontmatter: `name`, `description`, optional `allowed-tools`, `argument-hint`; `` !`cmd` `` injection | auto-loading + `/odoo-master:<skill>` | `test_structure`, `test_skill_injections_are_single_commands`, live session |
| `commands/*.md` (20) | Markdown + frontmatter: `description`, `argument-hint`, `allowed-tools` (YAML list), `disable-model-invocation`; `$ARGUMENTS`, `$0`/`$1` | `/odoo-master:<command>` | `test_commands_frontmatter_and_no_skill_collision`, live session |
| `hooks/hooks.json` | `{"hooks": {Event: [{matcher, hooks: [{type: command, command, timeout}]}]}}` | Claude Code hook runner | `claude plugin validate`, `test_hooks_json_targets_exist`, live session |
| `.mcp.json` | `{"mcpServers": {"odoo-master": {type: stdio, command, args, env}}}` | Claude Code MCP client | stdio probe test, live session (`connected`) |
| `.lsp.json` | `{"pyright": {command, args, extensionToLanguage, settings, startupTimeout, maxRestarts}}` | Claude Code LSP (diagnostics after edits) | key whitelist test; LSP handshake test with `pyright-langserver`. Needs `npm i -g pyright`; without it the server simply does not start |
| `monitors/monitors.json` | array of `{name, command, description, when}` | background monitor (interactive sessions only; not `-p`) | key/`when` test; `odoo-master watch` diff tests |
| `output-styles/odoo-engineer.md` | Markdown + frontmatter `name`, `description`, `keep-coding-instructions` | `/output-style odoo-master:odoo-engineer` | frontmatter test |
| `claude-workflows/odoo-parallel-review.js` | Claude Code dynamic workflow: `export const meta`, `agent()`, `pipeline()`, `log()` | `/odoo-master:odoo-parallel-review` | parse check; listed in a live session |
| `bin/odoo-master` | bash wrapper → `python3 -m odoo_master.cli` | Bash tool (on PATH while enabled), skills, commands, monitors | CLI tests |
| `workflows/*.yaml` (15) | `schemas/workflow.schema.json` | `odoo_master.workflow.engine` | `odoo-master workflow validate` (schema + semantic checks) |
| `schemas/*.schema.json` (10) | JSON Schema 2020-12 | CLI `schema`, engine, registry, estimate | `test_schemas_are_valid_jsonschema` |
| `policies/*.yaml` (7) | YAML | guard hook, engine, stop gate, evidence | loaded in tests; config schema |
| `config/defaults.yaml` | YAML (`schemas/config.schema.json`) | `odoo_master.config` | `test_routes_and_config_validate` |
| `knowledge/odoo-versions.yaml` | YAML: versions + rules {id, since, files, pattern, severity, fingerprint, message, doc} | version detection, validator, migration scan | regex compile tests; rules exercised on fixtures and live installs |
| `knowledge/standard-modules/*.json` | JSON extracted from the official images 16.0–20.0 (module depends; model → defining/extending modules) | validator (transitive deps), inventory, lookup, MCP server | lookup tests |
| `integrations/*/capabilities.yaml` | provider profiles: `server_patterns`, `tools[{match, capabilities, access}]` | MCP registry | registry tests |
| `integrations/events/routes.yaml` | `schemas/event-routes.schema.json` | event receiver | schema test, HTTP receiver test |
| `templates/**` | Markdown templates (frontmatter per `schemas/report.schema.json`), estimate JSON, `settings/project-settings.json` | agents, `odoo-master report`, `odoo-master init --settings` | referenced-template test, init merge test |
| `instructions/*.md` | Markdown | all agents (via `global.md` index) | referenced-instruction test |
| `evals/**/case.yaml`, `evals/mocks/**` | `claude plugin eval` schema 1.1; MCP mocks (`_tools.json`, `<tool>.md` with `expect`) | `claude plugin eval` | executed (see testing.md) |
| `tests/**` | pytest + fixtures (Odoo 16–20 projects, webhook payloads) and `tests/live/run_live_sessions.py` | CI / developers | — |

### About `settings.json`
The Claude Code docs read for this build don't describe a plugin-root `settings.json`, so the plugin doesn't ship
one, and it doesn't change the main agent or user settings. Recommended **project** permissions ship as
`templates/settings/project-settings.json`. `odoo-master init --settings` (or `/odoo-master:init --settings`) merges them
additively into `.claude/settings.json` after writing a `.bak` backup.
