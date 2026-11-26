---
name: mcp-integration
description: "Universal MCP integration: discover configured MCP servers and their tools (schemas, read/write classification), map tools to capabilities (ticket.*, repo.*, chat.*, docs.*, db.*, browser.*), register them, select tools dynamically for workflows, and handle auth problems, disconnections and missing capabilities. Use when connecting a new MCP server, when a workflow needs an external capability, or when an integration fails."
allowed-tools: "Bash(odoo-master *)"
---

# MCP integration

Configured servers (from .mcp.json / settings, no secrets): !`odoo-master --soft --max-lines 40 mcp servers`

## Discovery (runtime, not hard-coded)
1. **Session view** (authoritative for what you can call now): list the MCP tools available to you (names `mcp__<server>__<tool>`; use ToolSearch / tool listing). For each server collect name, description and input schema.
2. **Probe** stdio/unauthenticated HTTP servers directly: `odoo-master mcp probe` (JSON-RPC initialize + tools/list; annotations readOnlyHint/destructiveHint when provided). OAuth-protected servers can only be discovered from the session.
3. **Register**: write the collected tools as JSON `[{"name","server","description","inputSchema","annotations"}]` and run `odoo-master mcp register --tools tools.json`. The registry (`.odoo-master/mcp-registry.json`) classifies each tool:
   - provider (jira, github, slack, linear, notion, confluence, postgres, playwright, generic) from server name/tool patterns (`integrations/*/capabilities.yaml`);
   - capabilities (e.g. `ticket.search`, `ticket.add_comment`, `repo.create_pull_request`, `chat.reply_thread`);
   - access: `read`, `write`, `destructive` (annotations first, then verb heuristics).
4. **Resolve** in workflows: `odoo-master mcp resolve ticket.add_comment [--provider jira]`.

## Rules
- Never assume two servers support the same operation; read each tool's schema before calling.
- `write`/`destructive` tools are external actions → approval policy; `read` tools are free to use.
- Failures: the PostToolUseFailure hook logs them (`odoo-master mcp log`). Auth errors → ask the user to reconnect (/mcp); disconnection → continue with degraded capability and report it; never retry a write blindly.
- MCP is tool access, **not** an event subscription. Background triggers use webhooks/polling via `odoo-master events` (see docs/mcp-integrations.md).
- Credentials stay in the MCP server configuration; never copy them into files or prompts.
