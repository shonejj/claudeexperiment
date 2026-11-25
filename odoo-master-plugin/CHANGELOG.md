# Changelog

## 0.1.0 — 2026-11-25
First release.
- Project intelligence: inventory, architecture and dependency maps, multi-signal Odoo version detection (16.0–20.0).
- Knowledge: 21 version rules checked against official Odoo sources; standard module dependency graphs and model→module maps for 16.0–20.0.
- Static validator (manifest, XML, references against transitive dependencies, security, Python, JS, version rules).
- Docker runtime test runner (install + upgrade with Odoo tests), log summariser, ephemeral instances for visual QA.
- Read-only PostgreSQL inspection with production refusal.
- Migration scan and plan.
- Workflow engine + 15 workflows; native Claude Code parallel review workflow.
- 25 agents, 33 skills, 8 hook handlers, 7 policies, 10 JSON schemas, templates.
- MCP capability registry with stdio/HTTP probing and session registration; bundled read-only MCP server.
- Signed webhook receiver for GitHub, Slack, Jira and Linear, with dedupe and routing.
- Markdown→HTML→PDF reports with verification; evidence manifests.
- 71 pytest tests; 8 `claude plugin eval` cases with Jira MCP mocks.
