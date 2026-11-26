# Configuration

## Hierarchy (later wins)
1. Plugin defaults: `config/defaults.yaml`, plus policies in `policies/*.yaml` (exposed as `config.policies.<name>`)
2. Organisation file: path in `ODOO_MASTER_ORG_CONFIG`
3. Project file: `.odoo-master/config.yaml` (schema `schemas/config.schema.json`)
4. Plugin options (`claude plugin configure odoo-master`): `autonomy`, `production_patterns`, `default_odoo_version`, exported to hooks as `CLAUDE_PLUGIN_OPTION_*`
5. Environment: `ODOO_MASTER_AUTONOMY`, `ODOO_MASTER_PRODUCTION_PATTERNS`, `ODOO_MASTER_DEFAULT_ODOO_VERSION`

Inspect the merged result with `odoo-master config`.

**Enforcement is not configuration.** Organisation-level restrictions belong in Claude Code managed settings
(permissions, allowed MCP servers, disabled hooks) and in infrastructure (credentials scoped to dev/test). This
plugin's config shapes agent behaviour and guard-rails only.

## Options
| Key | Default | Meaning |
|---|---|---|
| `autonomy` | `checkpoint` | `checkpoint`: every approval gate waits for a human. `autonomous`: low-risk gates auto-approve (policy) |
| `production_patterns` | `[prod, production, live]` | regexes; matching database names/hosts are treated as production |
| `default_odoo_version` | `""` | used only when detection finds nothing |
| `agents.disabled` / `agents.optional_enabled` | `[]` | agent selection hints for the orchestrator |
| `workflows.default_for_intent` | see defaults | intent → workflow mapping |
| `runtime.image` / `postgres_image` / `enterprise_path` / `addons_paths` | auto | runtime test environment |
| `reports.formats` / `output_dir` | `[md, html, pdf]`, `.odoo-master/reports` | report outputs |
| `estimation.*` | hours per complexity, multipliers, overheads, hours/day | estimator model |
| `integrations.ticket_providers_priority` | `[jira, linear, github]` | which provider to prefer when several provide `ticket.*` |
| `integrations.project_repositories` | — | map ticket projects to repositories, e.g. `{INV: acme/odoo-inventory}` |
| `instructions.extra_files` | `[]` | project instruction files the agents must read |

## Policies (`policies/*.yaml`)
| File | Consumed by | Controls |
|---|---|---|
| `security.yaml` | guard hook, agents | protected (core) paths, secret patterns, privacy |
| `approvals.yaml` | workflow engine, orchestrator | auto-approve threshold, always-human actions, ticket approval signals |
| `database-safety.yaml` | guard hook, `odoo-master db` | destructive SQL patterns, production checks |
| `git-safety.yaml` | guard hook | denied / confirmation-required git commands, protected branches |
| `deployment-safety.yaml` | guard hook, devops agent | destructive deployment commands |
| `testing.yaml` | Stop-hook quality gate, evidence | blocking severities, max blocks, required verification levels per intent |
| `evidence.yaml` | evidence + reports | required evidence, honesty rules |
Override any key in `.odoo-master/config.yaml` under `policies:`, for example:
```yaml
autonomy: autonomous
policies:
  approvals:
    autonomous: {max_auto_approve_risk: medium}
  testing:
    quality_gate: {max_blocks_per_session: 2}
```

## Custom components
- Workflows: `.odoo-master/workflows/<name>.yaml` (same name overrides).
- MCP provider mappings: `.odoo-master/integrations/<provider>.yaml` (format of `integrations/jira/capabilities.yaml`).
- Event routes: `.odoo-master/events/routes.yaml`.
- Agents/skills: project `.claude/agents/` and `.claude/skills/` (Claude Code precedence rules).

## Environment variables
| Variable | Used by |
|---|---|
| `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PROJECT_DIR` | set by Claude Code; respected by the CLI |
| `ODOO_MASTER_PYTHON` | interpreter for `bin/odoo-master` |
| `ODOO_MASTER_ORG_CONFIG` | organisation config file |
| `ODOO_MASTER_AUTONOMY`, `ODOO_MASTER_PRODUCTION_PATTERNS`, `ODOO_MASTER_DEFAULT_ODOO_VERSION` | config overrides |
| `ODOO_MASTER_GITHUB_WEBHOOK_SECRET`, `ODOO_MASTER_SLACK_SIGNING_SECRET`, `ODOO_MASTER_JIRA_WEBHOOK_SECRET`, `ODOO_MASTER_LINEAR_WEBHOOK_SECRET` | event receiver signature secrets (names configurable in routes) |
| `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`/`~/.pgpass`, `PGDATABASE` | read-only database inspection |
| `PLAYWRIGHT_CHROMIUM_EXECUTABLE` | custom Chromium for visual QA / PDF |
