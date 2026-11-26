---
description: "Discover connected MCP servers and their tools, classify capabilities (ticket/repo/chat/docs/db/browser) and register them for workflows."
argument-hint: "[probe|register|resolve <capability>]"
allowed-tools:
  - "Bash(odoo-master *)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/bin/odoo-master *)"
disable-model-invocation: true
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

!`${CLAUDE_PLUGIN_ROOT}/bin/odoo-master --soft --max-lines 40 mcp servers`

Follow the `mcp-integration` skill: list the MCP tools available in this session, write them to `.odoo-master/session/tools.json`, run `odoo-master mcp register --tools .odoo-master/session/tools.json` and `odoo-master mcp probe` for stdio servers, then show the capability table (provider, capability, tool, read/write/destructive) and which workflow capabilities are still missing. Argument: $ARGUMENTS
