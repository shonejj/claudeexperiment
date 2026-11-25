# Workflows

Workflow definitions live in `workflows/*.yaml` and are validated against `schemas/workflow.schema.json` plus semantic checks: agents and skills exist, `needs` and `retry_from` refer to real steps, no cycles, and only safe expressions are used.
Project workflows in `.odoo-master/workflows/<name>.yaml` override plugin workflows with the same name.

## Engine semantics
- **Steps**: `task` (an agent does work), `approval` (a gate), `notify` (an external update through an MCP capability).
- **Order**: `needs`. All ready steps are returned together and run in parallel; `parallel_group` is a display hint.
- **Conditions**: `when` uses a sandboxed expression over `ctx`, `inputs` and `config`. False means the step is SKIPPED, and an upstream failure propagates as a skip.
- **Retries**: `retries` re-dispatches a failed step. `on_failure: {retry_from: <step>, max_loops: N}` resets the chain from that step (the repair loop). `on_failure: continue` records the failure as a concern and carries on.
- **Timeouts**: `timeout_minutes` per step or in `defaults`. An expired RUNNING step becomes TIMED_OUT on the next `workflow next`.
- **Approvals**: in `checkpoint` mode every gate waits for `workflow approve --by <who>`. In `autonomous` mode a gate auto-approves only when risk ≤ `policies/approvals.yaml` `autonomous.max_auto_approve_risk` and `auto_approve_when` holds. Gates marked `always_human` never auto-approve. `on_reject` loops back to a step.
- **Checkpoints**: `.odoo-master/executions/<id>.json` plus an `.events.jsonl` log. Resume with `workflow next -e <id>`; cancel with `workflow cancel`.
- **Ticket identity**: `--ticket` or `inputs.ticket` is stored on the execution and must appear on every artifact.

## Shipped workflows

| Workflow | Intents | Triggers | Steps | Description |
|---|---|---|---|---|
| `bug-fix` | bug_fix | interactive, odoo.test.failed | intake → investigate → fix-approval → regression-test → fix → verify → review → report → ticket-update | Reproduce, root-cause, fix and regression-test a defect in an existing Odoo customisation. |
| `code-review` | code_review | interactive | static → review → security → summary | Independent review of local changes (working tree or branch diff) with Odoo static validation and two verdicts (spec compliance, quality). |
| `database-investigation` | database_investigation | interactive | intake → access-approval → inspect → remediation-plan → remediation-approval → review → report | Investigate a PostgreSQL/ORM issue (data inconsistency, constraint errors, locks, missing columns) read-only, then propose a safe remediation. |
| `deployment` | deployment | interactive, odoo.deployment.requested | intake → prepare → staging-run → deploy-approval → handover | Prepare (never perform unapproved) an Odoo deployment - module upgrade list, config review, backup evidence, staging run, rollback. |
| `existing-module-enhancement` | module_enhancement | interactive | intake → locate → plan → plan-approval → implement → migration-scripts → validate → runtime-tests → review → report → ticket-update | Extend an existing custom module (fields, views, logic) while preserving its architecture and data. |
| `general-development` | general_software | interactive | intake → plan → plan-approval → implement → test → review → report | Non-Odoo software task in any repository - plan, implement with tests, review, evidence. |
| `github-issue-development` | github_issue | interactive, github.issue.labeled, github.issue.created | read-issue → analyse → plan → plan-approval → implement → verify → review → pull-request | Plan and implement a GitHub issue in the connected repository, then open a pull request linked to it. |
| `jira-ticket-development` | ticket_implementation | interactive, jira.issue.status_changed, jira.issue.labeled | confirm-approval → approval → branch → implement → verify → review → report → pull-request → ticket-complete | Implement an approved ticket end-to-end - branch, code, tests, review, evidence, PR, ticket update - keeping the ticket id on every artifact. |
| `jira-ticket-planning` | ticket_planning | interactive, jira.issue.labeled, jira.issue.assigned, jira.issue.created, linear.issue.labeled | capabilities → read-ticket → analyse-repo → actionability → technical-plan → post-approval → post-plan | Read a ticket (Jira/Linear/GitHub via discovered MCP capabilities), analyse the linked Odoo repository and post a technical plan + estimate back to the same ticket. |
| `new-odoo-module` | new_module | interactive, odoo.module.development.requested | intake → requirements → reuse-check → design → estimate → plan-approval → scaffold-and-implement → frontend → static-validation → runtime-tests → visual-qa → review → security-review → report → ticket-update | Build a new custom Odoo module only after confirming no standard feature or existing custom module can be extended instead. |
| `odoo-migration` | migration | interactive, odoo.migration.requested | intake → scan → db-impact → plan-approval → port → validate → runtime → review → db-review → report | Port custom modules between Odoo major versions, one hop at a time, with database migration scripts, validation and rollback plan. |
| `performance-optimization` | performance | interactive | intake → measure → plan-approval → optimize → verify → review → report | Measure, locate and fix Odoo performance problems (N+1 queries, missing indexes, heavy computes, slow views). |
| `pull-request-review` | pull_request_review | interactive, github.pull_request.opened, github.pull_request.updated | fetch → static → code-review → security-review → db-review → post-approval → post-review | Review an existing pull request with Odoo-aware checks (version rules, ACLs, migrations, tests, CI) and report findings. |
| `security-audit` | security_audit | interactive | intake → static-scan → acl-review → code-audit → report | Audit custom modules for access-control gaps, record-rule leaks, unsafe sudo, SQL injection, public routes and secret handling. |
| `slack-issue-investigation` | slack_report | interactive, slack.message.received | read-thread → dedupe → investigate → ticket-approval → ticket → reply | Turn an Odoo issue reported in a chat thread into a deduplicated ticket and a root-cause summary posted back to the same thread. |

## Native Claude Code workflow
`claude-workflows/odoo-parallel-review.js` (`/odoo-master:odoo-parallel-review`) is a Claude Code dynamic workflow. It runs three independent reviewers (quality, security, database) in parallel with structured output and merges their findings. It complements the YAML engine; it does not replace it.

## CLI
```
odoo-master workflow list | validate [name]
odoo-master workflow start <name> -i key=value ... [--ticket KEY]
odoo-master workflow next -e <id>
odoo-master workflow complete -e <id> --step <s> --status DONE|DONE_WITH_CONCERNS|NEEDS_CONTEXT|BLOCKED|FAILED [--output out.json] [--note ...]
odoo-master workflow approve -e <id> --step <gate> --by "<who>" [--decision rejected --note ...]
odoo-master workflow set -e <id> -i key=value     # supply context after NEEDS_CONTEXT/BLOCKED
odoo-master workflow status|cancel -e <id>
odoo-master workflow executions
```
