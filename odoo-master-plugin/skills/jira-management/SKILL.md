---
name: jira-management
description: "Ticket lifecycle through any connected ticketing MCP server (Jira, Linear, GitHub Issues, others): discover tools by capability, search/read and normalise tickets, check approval signals, post plan/progress/completion comments to the same ticket, link reports and PRs, and transition only when authorised. Use for anything involving a ticket key, ticket URL or 'my tickets'."
---

# Ticket management (Jira & compatible)

## 0. Capabilities, not tool names
`odoo-master mcp resolve ticket.search` / `ticket.read` / `ticket.add_comment` / `ticket.transition` / `ticket.create`
→ returns matching tools per server with access class. No match → run the `mcp-integration` skill (discovery). Still none → tell the user which capability is missing and continue with what is possible (e.g. produce the plan locally).
Always read the tool's input schema before the first call; providers differ (JQL for Jira, filters for Linear).

## 1. Find & read
- "assigned to me about inventory errors": search (Jira JQL e.g. `assignee = currentUser() AND statusCategory != Done AND text ~ "inventory"`), list candidates; **ambiguous → ask**.
- Read description, comments, attachments list, links, labels, status. Normalise to `schemas/ticket.schema.json` in `.odoo-master/plans/<KEY>/ticket.json`.
- Identify the repository: ticket links/fields, project mapping in `.odoo-master/config.yaml` (`integrations.project_repositories`), or ask.

## 2. Plan comment
Fill `${CLAUDE_PLUGIN_ROOT}/templates/jira-comments/plan-comment.md`; attach/link the PDF (`odoo-master report ... --formats pdf`) if the server supports attachments, else reference the repo path/PR.
Footer always: `odoo-master execution <id> · ticket <KEY>`.

## 3. Approval
Per `policies/approvals.yaml` `ticket_approval`: label, status, or approver comment. Record `workflow approve --by "<approver> via <ticket URL>"`.

## 4. Progress & completion
`templates/jira-comments/completion-comment.md`: changed modules/files, branch, PR, tests + levels, screenshots, migration notes, deployment notes, unresolved issues, evidence link.
Transition only when configured **and** acceptance criteria verified. Never close because work started.

## Guardrails
- Re-check the ticket key before every write; never write to an unrelated ticket.
- Respect visibility: no secrets, no production personal data in comments.
- Writes are external actions: in checkpoint mode show the comment before posting.
