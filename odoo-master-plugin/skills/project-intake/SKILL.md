---
name: project-intake
description: "Entry point for any request in an Odoo (or other) repository: establishes project facts, classifies the request (new module, enhancement, bug, migration, database, performance, security, deployment, ticket, PR review, general software), selects the workflow and agents, and starts it. Use whenever a user describes work to be done and no workflow is running."
argument-hint: "[request]"
---

# Project intake

Current project facts (generated now):
!`"${CLAUDE_PLUGIN_ROOT}/bin/odoo-master" analyze --brief 2>/dev/null || echo "analysis unavailable"`

Request: $ARGUMENTS

## Procedure
1. **Facts first.** Read `.odoo-master/project-context.md`. If the Odoo version has conflicts or is unknown, ask the user before any planning (show the signals).
2. **Classify** — run `odoo-master classify "<request>"` for deterministic signals (mentioned modules/models, ticket refs, keywords, existing module matches), then decide with judgement:
   | Intent | Typical signals | Workflow |
   |---|---|---|
   | new_module | "new module/app", no matching custom module | `new-odoo-module` |
   | module_enhancement | names an existing module/model/view | `existing-module-enhancement` |
   | bug_fix | error, traceback, "fix", "broken" | `bug-fix` |
   | migration | two versions, "upgrade", "port" | `odoo-migration` |
   | database_investigation | SQL, constraint, data inconsistency | `database-investigation` |
   | performance | slow, timeout, N+1 | `performance-optimization` |
   | security_audit | access, permissions audit | `security-audit` |
   | deployment | deploy, staging, production | `deployment` |
   | ticket_planning / ticket_implementation | ticket key/URL + plan/implement | `jira-ticket-planning` / `jira-ticket-development` |
   | github_issue / pull_request_review | issue/PR URL | `github-issue-development` / `pull-request-review` |
   | slack_report | Slack permalink | `slack-issue-investigation` |
   | general_software | no Odoo modules involved | `general-development` |
   The project config may override the mapping (`workflows.default_for_intent`).
3. **Do not assume a new module.** Prefer: configuration → existing custom module → inheritance in a new small module → brand-new module (see `instructions/odoo-development.md`, reuse ladder).
4. **Record** the classification (intent, module(s), version, complexity, risk, agents, integrations, approvals, deliverables) in the execution inputs.
5. **Start** `odoo-master workflow start <workflow> -i request="..." [--ticket KEY]` and follow the `workflow-execution` skill.
6. Trivial questions ("what does field X do?") need no workflow — answer directly with path:line citations.

## Classification output (keep in the execution context)
```json
{"intent": "...", "modules": ["..."], "odoo_version": "18.0", "complexity": "simple|moderate|complex",
 "risk": "low|medium|high|critical", "agents": ["..."], "integrations": ["jira"], "approvals": ["plan"],
 "deliverables": ["..."], "estimated_effort": "see estimation skill"}
```
