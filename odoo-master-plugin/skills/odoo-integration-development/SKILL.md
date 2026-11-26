---
name: odoo-integration-development
description: "Integrating Odoo with external systems: Odoo external APIs (XML-RPC/JSON-RPC, JSON-2 API keys), outbound REST calls from Odoo modules, inbound webhooks, sync jobs with crons/queues, idempotency, retries and credential handling. Use when building connectors or APIs around Odoo."
---

# Odoo integration development

## Inbound (external → Odoo)
- Prefer Odoo's external API with an API key of a dedicated integration user (least privilege groups).
- Webhook controller: `auth="none"`/`"public"`, `csrf=False`, verify HMAC signature with a secret from `ir.config_parameter` (never hard-coded), constant-time compare, replay protection (timestamp/nonce), idempotency key stored on the target record.
## Outbound (Odoo → external)
- `requests` with timeouts, retries with backoff for idempotent calls, structured logging without secrets/PII.
- Long or bulk sync in `ir.cron` with batches and commit progress; keep a sync state field per record (`x_sync_state`, last error).
- Configuration via `res.config.settings` + `ir.config_parameter`.
## Testing
- Mock HTTP (`unittest.mock.patch("...requests.post")`) in Odoo tests; never call real external services in tests.
## Agentic side
- External tools for the agents themselves come through MCP (`mcp-integration` skill). Event delivery (webhooks into the agent system) goes through `odoo-master events`, not MCP.
