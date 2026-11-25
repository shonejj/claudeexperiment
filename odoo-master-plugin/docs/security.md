# Security

## Boundaries (what protects what)
| Layer | Enforces | Strength |
|---|---|---|
| Claude Code permissions / managed settings | which tools and commands may run | **boundary** (organisation-controlled) |
| Infrastructure | credentials scoped to dev/test, network access, database roles | **boundary** |
| Plugin hooks (guard, stop gate) | deny or ask on dangerous commands, core-file edits and secrets; quality gate | guard-rail (fail-open on internal errors) |
| Plugin policies and instructions | agent behaviour | guidance only |
Plugin instructions are not a security boundary. To keep agents away from production, give them no production credentials.

## Guard hook (PreToolUse)
- Git: force push and history rewrites denied; reset, clean, merge and branch deletion ask.
- Database: DROP, TRUNCATE, DELETE without WHERE, `dropdb`, `db drop`, `neutralize` ask. Writes or upgrades against production-looking databases are denied.
- Deployment: destructive volume or compose commands ask.
- Secrets: printing `.env`, `.pgpass`, keys or `odoo.conf`, or dumping the environment, asks. Hard-coded secret patterns in edits ask.
- Core protection: edits under Odoo/Enterprise source paths, or paths detected as core by the inventory, ask with an inheritance reminder.
- In non-interactive permission modes (`bypassPermissions`, `dontAsk`), "ask" becomes "deny".

## Data handling
- Redaction of passwords, tokens, keys and DSNs in logs, reports, rendered HTML/PDF and MCP failure logs.
- MCP call logs store metadata only (tool, server, duration, ok, redacted error), never inputs or outputs.
- Public chat channels receive summaries without private ticket data.
- Database access is read-only, and production targets are refused without approval.
- Event receiver: HMAC verification is mandatory (no secret means no events), Slack replay window, payload size limit, binds to localhost by default.

## Odoo application security
See `instructions/odoo-security.md` and the `odoo-security` skill. The validator checks for missing ACLs,
group-less ACLs, record-rule syntax, SQL built by string formatting, `eval`, removed APIs, and overrides without `super()`.
