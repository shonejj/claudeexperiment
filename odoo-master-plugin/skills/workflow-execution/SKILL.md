---
name: workflow-execution
description: "Drives a workflow execution with the odoo-master engine: start, next, dispatch ready steps (in parallel), complete with statuses, approval gates, repair loops, resume after compaction. Use when running or resuming any odoo-master workflow."
allowed-tools:
  - "Bash(odoo-master *)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/bin/odoo-master *)"
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

# Workflow execution

Active executions: !`${CLAUDE_PLUGIN_ROOT}/bin/odoo-master --soft --max-lines 40 workflow executions`

## Loop
```
odoo-master workflow start <name> -i key=value ... [--ticket KEY]   # returns ready steps
while status in (running, waiting_approval):
    for each step in ready (same parallel_group → dispatch together):
        Agent(subagent_type="odoo-master:<agent>", prompt=<brief>)
        write the agent's structured output to .odoo-master/executions/<id>/<step>.json
        odoo-master workflow complete -e <id> --step <step> --status <STATUS> --output <file> [--note "..."]
    for each waiting_approval:
        present `present:` artifacts; wait for the human (checkpoint) →
        odoo-master workflow approve -e <id> --step <gate> --by "<name or URL>" [--decision rejected --note "..."]
```
- `STATUS` ∈ DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT, BLOCKED, FAILED (agent reporting contract).
- NEEDS_CONTEXT/BLOCKED: obtain the fact, `odoo-master workflow set -e <id> -i key=value`, then `workflow next`.
- FAILED: the engine retries (`retries`) and then follows `on_failure` — `retry_from` resets the implementation chain (bounded repair loop, `max_loops`).
- Timeouts: running steps past their deadline become TIMED_OUT on the next `workflow next`.
- Put `risk` in step outputs (`low|medium|high|critical`); approval gates use it. In `autonomous` mode only low-risk gates (policy) auto-approve; `always_human` gates never do.
- Cancel: `odoo-master workflow cancel -e <id> --note reason`.

## Brief for each dispatched agent
execution id, step id, ticket key, Odoo version, modules, the step `instructions`, required `outputs`, paths of context artifacts, and the reporting contract. Never paste secrets.

## Resume after compaction / new session
`odoo-master workflow executions` → `odoo-master workflow status -e <id>` → `workflow next -e <id>` (idempotent: re-lists RUNNING steps).
