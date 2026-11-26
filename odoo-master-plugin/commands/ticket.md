---
description: "Plan or implement a ticket (Jira, Linear, GitHub issue) end to end via the connected MCP servers, keeping the ticket id on every artifact."
argument-hint: "<KEY-123 or URL> [plan|implement]"
allowed-tools:
  - "Bash(odoo-master *)"
disable-model-invocation: true
---

Ticket: $0 — mode: $1 (default: plan)
Use the `jira-management` skill. Resolve capabilities first (`odoo-master mcp resolve ticket.read`). Mode `plan` → workflow `jira-ticket-planning`; mode `implement` → `jira-ticket-development` (requires the configured approval signal on the ticket). Never touch any other ticket.
