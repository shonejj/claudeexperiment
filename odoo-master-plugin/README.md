# Odoo Master — Claude Code plugin

An agentic Odoo engineering team inside Claude Code. It works out which Odoo version a project targets,
understands existing repositories before changing them, plans and estimates work, implements changes through
inheritance (never by editing Odoo core), tests in real Odoo containers, reviews, collects evidence, and reports
back to the place the work came from: the terminal, Jira, GitHub or Slack.

Supports **Odoo 16.0, 17.0, 18.0, 19.0 and 20.0** (Community and Enterprise projects, Docker, Odoo.sh or
self-hosted), plus general software repositories.

## What you get
| Area | Components |
|---|---|
| Project intelligence | `odoo-master analyze` → `.odoo-master/` (inventory, architecture map, dependency map, version evidence, context brief). Separates code-level facts from database-level facts |
| Version intelligence | multi-signal detection with confidence and conflicts; a rule table of 21 breaking changes across 16→20 checked against real Odoo source; standard module and model maps for every series |
| Validation | manifest, XML/XPath, references against transitive dependencies, ACL/`ir.access`, record rules, SQL injection, `eval`, `super()`, removed APIs, JS syntax |
| Runtime testing | `odoo-master runtime test`: disposable PostgreSQL + official `odoo:<series>` image, install and upgrade passes with `--test-tags`, log summary. "0 tests" is never a pass |
| Visual QA | Playwright login on a disposable instance, screenshots at several widths, console and network errors |
| Database | read-only `psql` inspection (installed modules, ORM↔schema drift, indexes, locks, sizes), production refusal |
| Migration | hop-by-hop scan and plan, `upgrade_code` guidance, upgrade-script standards, rollback |
| Commands | 20 slash commands (`/odoo-master:analyze`, `status`, `plan`, `build`, `fix`, `test`, `scaffold`, `migrate`, `upgrade-code`, `review`, `approve`, `resume`, `ticket`, `mcp`, `events`, `lookup`, `doctor`, `init`, `validate`, `report`) |
| Scaffolding | `odoo-master scaffold`: version-correct module generator, install/upgrade/test-verified on official images 16.0–20.0 |
| Standard source | `odoo-master source grep/show` and `lookup` read the exact series' standard code in the official image (no clone); `source upgrade-code` runs Odoo's own `upgrade_code` |
| Agents | 25 specialists (orchestrator, architect, developers, OWL, database, migration, security, QA, reviewers, DevOps, Jira, GitHub, docs) |
| Skills | 33 skills: the Odoo knowledge base and engineering procedures |
| Workflows | 15 schema-validated YAML workflows run by an engine with parallel steps, conditions, approval gates, retries, repair loops, timeouts, checkpoints and resume; plus one native Claude Code parallel-review workflow |
| Hooks | 12 handlers on 10 events (verified in real Claude Code sessions): session bootstrap and resume, safety guard (git, database, deployment, secrets, core files), per-edit validation, automatic evidence capture, subagent context injection and STATUS contract, Stop quality gate, compaction ledger, ticket detection, MCP call logging, session summary |
| Other components | output style `odoo-engineer`, monitor (approval/event notifications), `.lsp.json` (pyright diagnostics), 7 plugin options, recommended project permissions (`odoo-master init --settings`) |
| MCP | discovers capabilities at runtime for any server (Jira, GitHub, Slack, Linear, Notion, Postgres, Playwright, or your own); bundled read-only `odoo-master` MCP server |
| Events | signed webhook receiver for GitHub, Slack, Jira and Linear, with dedupe, routing and execution records; runs `claude -p` when dispatch is enabled |
| Reports | Markdown → HTML → verified PDF, templates for plans, comments, reports, runbooks and migration plans; evidence manifests with sha256 |
| Safety | policies, approval modes (`checkpoint` / `autonomous`), redaction, an honest record of which verification levels ran |

## Quick start
```
/plugin marketplace add shonejj/claudeexperiment
/plugin install odoo-master@odoo-master
```
In an Odoo repository:
```
/odoo-master:project-intake Add a "quality state" to receipts and block validation while checks are pending
/odoo-master:odoo-migration migrate sale_discount_approval from 16.0 to 18.0
/odoo-master:jira-management find my Jira ticket about inventory errors and post a plan
```
Slash commands: `/odoo-master:doctor`, `/odoo-master:analyze`, `/odoo-master:plan ...`, `/odoo-master:status`.
Or use the CLI directly: `odoo-master analyze --brief`, `odoo-master validate --brief`,
`odoo-master runtime test --modules my_module`, `odoo-master migration plan --from 16.0 --to 19.0`.

## Documentation
[architecture](docs/architecture.md) · [components](docs/components.md) · [commands](docs/commands.md) · [hooks](docs/hooks.md) · [installation](docs/installation.md) · [configuration](docs/configuration.md) ·
[Odoo support](docs/odoo-support.md) · [agents](docs/agents.md) · [skills](docs/skills.md) · [workflows](docs/workflows.md) ·
[MCP](docs/mcp-integrations.md) · [Jira](docs/jira-integration.md) · [GitHub](docs/github-integration.md) ·
[security](docs/security.md) · [migration](docs/migration.md) · [testing](docs/testing.md) · [troubleshooting](docs/troubleshooting.md)

Research: `../docs/research/` (plugin comparison and Odoo architecture, development, database, migration, deployment and version compatibility).

## Layout
```
.claude-plugin/plugin.json   agents/ (25)   skills/ (33)   commands/ (20)   hooks/hooks.json   .mcp.json   .lsp.json
monitors/monitors.json   output-styles/   bin/odoo-master
claude-workflows/ (native JS workflow)   workflows/ (YAML engine definitions)   scripts/odoo_master/ (core)
knowledge/ (version rules + standard module maps)   integrations/ (capability profiles, event routes)
policies/ config/ instructions/ templates/ schemas/ evals/ tests/ docs/
```
Differences from the requested structure: the YAML workflows stay in `workflows/`, and the manifest points
Claude Code's native `workflows` component at `claude-workflows/`, because Claude Code treats `workflows/` as
JavaScript workflows. Scripts are one Python package (`scripts/odoo_master/{odoo,mcp,workflow,integrations,reporting,planning,hooks,runtime}`)
behind one CLI, rather than one folder per script. Behaviour is the same and easier to test.

## License
MIT. Ideas adopted from Superpowers, Ponytail, Caveman, taste-skill and unclecatvn/agent-skills are credited in
`docs/research/plugin-comparison.md`; no code was copied from them.
