---
name: slack-triage
description: "Handling Odoo issues reported in Slack (or other chat) through MCP: read the message and thread, extract the issue, search for duplicate tickets, investigate the code, create or update a ticket when authorised, and reply in the original thread without leaking private data. Use for Slack permalinks or chat-reported problems."
---

# Slack triage

1. Resolve `chat.read_thread`, `chat.search`, `chat.reply_thread` (`odoo-master mcp resolve ...`).
2. Read the root message + replies; extract: symptom, error text, module/app, affected users, since when, environment (prod/staging), screenshots mentioned. Note channel visibility (public/private/DM).
3. Duplicate check: ticket search by error text/module; also search the channel for earlier reports.
4. Investigate via `debugging` + `odoo-project-analysis` (code-level; database only if authorised).
5. With approval: create a ticket (capability `ticket.create`) or comment on the duplicate; include the thread permalink.
6. Reply in the **same thread** (never a new top-level message): summary, likely cause, ticket link, next step. Public channels: no customer data, no internal ticket details beyond the link.
7. Avoid duplicate notifications: record posted message ids in the execution; check before posting again.
