---
description: "Discover connected MCP servers and their tools, classify capabilities (ticket/repo/chat/docs/db/browser) and register them for workflows."
argument-hint: "[probe|register|resolve <capability>]"
allowed-tools:
  - "Bash(odoo-master *)"
disable-model-invocation: true
---

!`odoo-master --soft --max-lines 40 mcp servers`

Follow the `mcp-integration` skill: list the MCP tools available in this session, write them to `.odoo-master/session/tools.json`, run `odoo-master mcp register --tools .odoo-master/session/tools.json` and `odoo-master mcp probe` for stdio servers, then show the capability table (provider, capability, tool, read/write/destructive) and which workflow capabilities are still missing. Argument: $ARGUMENTS
