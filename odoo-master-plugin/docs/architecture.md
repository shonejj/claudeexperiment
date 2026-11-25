# Architecture

Odoo Master is a Claude Code plugin built on a **harness-independent core**. The core is a Python
package (`scripts/odoo_master`, standard library plus PyYAML and jsonschema) that holds every
deterministic capability: facts, validation, workflow state, the MCP registry, event intake, reports
and evidence. The Claude Code layer (agents, skills, hooks, native workflow, `.mcp.json`) adds judgement
and orchestration on top of that core. It does not reimplement the core.

```mermaid
flowchart TB
  subgraph Entry["Entry points"]
    U[User in Claude Code] --> SK[/odoo-master:project-intake/]
    EV[Webhooks: Jira, GitHub, Slack, Linear] --> RCV[odoo-master events serve]
    RCV -->|record or claude -p| WFX
  end
  subgraph CC["Claude Code layer (adapter)"]
    SK --> ORC[orchestrator agent]
    ORC --> WFX[workflow-execution skill]
    WFX -->|Agent tool, parallel| AG[25 specialist agents]
    AG --> SKL[33 skills: knowledge and procedures]
    HK[hooks: SessionStart, Guard, PostEdit, Stop gate, PreCompact, Prompt, MCP log]
    NW[native JS workflow: odoo-parallel-review]
  end
  subgraph Core["Harness-independent core (scripts/odoo_master)"]
    PI[project.py + repository.py] --> KM[(.odoo-master/*.json, project-context.md)]
    VI[odoo/version.py] --> KN[(knowledge/odoo-versions.yaml + standard-modules/*.json)]
    VA[odoo/validate.py]
    MI[odoo/migration.py]
    RT[odoo/runtime.py: Docker Odoo + Postgres]
    DB[odoo/db.py: read-only psql]
    WE[workflow/engine.py] --> EXR[(executions/*.json checkpoints)]
    MR[mcp/registry.py + client.py] --> REG[(mcp-registry.json)]
    EVT[integrations/events.py]
    RP[reporting: md to html to pdf, evidence]
    PL[planning: classify, estimate]
  end
  AG -->|odoo-master CLI| Core
  HK --> Core
  MCPS[bundled MCP server odoo-master] --> Core
  Other[Other harnesses: Codex, Hermes, Pi] -.->|MCP or CLI| MCPS
```

## Layers and where they live

| Layer (brief) | Implementation | Replaceable by |
|---|---|---|
| Intelligence & orchestration | `agents/orchestrator.md`, `skills/project-intake`, `skills/workflow-execution` | another orchestrator agent or a custom workflow |
| Project understanding | `project.py`, `repository.py`, `odoo/inventory.py` → `.odoo-master/` | — (deterministic) |
| Odoo version intelligence | `odoo/version.py`, `knowledge/odoo-versions.yaml`, `knowledge/standard-modules/` | edit the YAML rules; regenerate the standard maps from new images |
| Requirements, planning, estimation | `requirements-analyst`, `solution-architect`, `planning/classify.py`, `planning/estimate.py`, `config.estimation` | config values, templates |
| Agents & workers | `agents/*.md` (25) | project `.claude/agents/` overrides (higher precedence) |
| Skills & knowledge | `skills/*/SKILL.md` (33), `instructions/`, `docs/research/` | project skills, `instructions.extra_files` |
| Workflow engine | `workflow/engine.py`, `workflows/*.yaml`, `schemas/workflow.schema.json` | project workflows in `.odoo-master/workflows/` (same name overrides) |
| Hooks & automation | `hooks/hooks.json` → `scripts/hook.py` → `odoo_master/hooks/*` | disable the plugin hook or override policies |
| MCP integration | `mcp/registry.py`, `mcp/client.py`, `integrations/*/capabilities.yaml`, bundled `mcp/server.py` | provider profiles in `.odoo-master/integrations/*.yaml` |
| GitHub / Jira / Slack | capability profiles + `github-agent`, `jira-agent`, `integration-engineer` and their skills | any MCP server that provides the capabilities |
| Testing & QA | `odoo/validate.py`, `odoo/runtime.py`, `odoo/logs.py`, `qa-engineer`, `test-automation-engineer` | runtime image/config |
| Visual verification | `scripts/visual/odoo_check.mjs` (Playwright), `visual-qa-engineer` | Playwright MCP |
| Database intelligence | `odoo/db.py` (read-only psql), `odoo-database-engineer`, `database-reviewer` | a Postgres MCP server (capability `db.query`) |
| Migration intelligence | `odoo/migration.py`, rules, `odoo-migration-specialist` | rule table |
| Documentation, reporting & evidence | `reporting/render.py`, `reporting/evidence.py`, `templates/` | templates, PDF engine order |
| Security & guardrails | `policies/*.yaml`, `hooks/guard.py`, `stop_gate.py`, native permissions | managed settings (organisation boundary) |
| Configuration & policy | `config/defaults.yaml` → org file → `.odoo-master/config.yaml` → plugin options → env | every level |
| Platform integration (SaaS/PaaS) | `integrations/events.py` (authenticated intake, dedupe, execution records), `runtime/` adapters | a hosted receiver that implements the same record format |

## Request lifecycle (interactive)

```mermaid
sequenceDiagram
  participant U as User
  participant O as orchestrator
  participant C as odoo-master CLI
  participant A as specialist agents
  U->>O: "Fix the error in my accounting customisation"
  O->>C: analyze --brief / classify
  C-->>O: version, modules, intent candidates
  O->>C: workflow start bug-fix
  loop until completed or a gate
    C-->>O: ready steps (parallel groups)
    O->>A: dispatch briefs (Agent tool)
    A->>C: validate / runtime test / evidence add
    A-->>O: STATUS + outputs
    O->>C: workflow complete --step ...
  end
  C-->>O: waiting_approval (plan gate)
  O->>U: plan, estimate, risks
  U->>O: approve
  O->>C: workflow approve --by "User"
```

## Event-driven lifecycle (tickets)

```mermaid
sequenceDiagram
  participant J as Jira
  participant R as events receiver
  participant X as claude -p (headless)
  participant M as Jira MCP server
  J->>R: webhook (label odoo-master), HMAC signed
  R->>R: verify signature, normalise, dedupe, route
  R->>R: execution request record (+ dispatch if mode=execute)
  R->>X: claude -p "/odoo-master:workflow-execution ... jira-ticket-planning ticket=INV-42"
  X->>M: ticket.read (capability resolved at runtime)
  X->>X: analyse repo, plan, estimate, render PDF
  X->>M: ticket.add_comment (same ticket, after approval policy)
  J->>R: label odoo-master:approved
  R->>X: jira-ticket-development ...
```

MCP is a tool protocol. It is **not** an event bus, so connecting a Jira MCP server never starts a
listener. Events come from webhooks into the receiver, or from a scheduled `claude -p` poll. See
`docs/mcp-integrations.md`.

## Execution state and resumability
- Every workflow execution is a JSON checkpoint plus an append-only event log in `.odoo-master/executions/`.
- `workflow next` is idempotent: it re-lists running steps, applies timeouts, evaluates conditions and approvals.
- The SessionStart hook (also on `compact`) re-injects active executions, and the PreCompact hook tells
  compaction to keep the ids. Together these let a long run survive context compaction (an idea taken
  from Superpowers' bootstrap-on-compact).

## Portability
The core never imports Claude Code code. Two seams expose it:
1. **CLI** (`bin/odoo-master`): usable from any harness that can run shell commands.
2. **MCP server** (`.mcp.json` → `odoo_master.mcp.server`): read-only project intelligence for any MCP-capable runtime.
`odoo_master/runtime/__init__.py` defines the `HarnessAdapter` interface. Only `ClaudeCodeAdapter` is
implemented. Agent and workflow definitions are Markdown/YAML; skills follow the open SKILL.md format.
