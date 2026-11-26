---
name: documentation
description: "Producing project documents from templates: requirements, functional/technical specs, implementation plans, migration plans, development reports, runbooks, release notes, with frontmatter metadata and Markdown→HTML/PDF rendering through odoo-master report. Use for any written deliverable."
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

# Documentation

- Templates: `${CLAUDE_PLUGIN_ROOT}/templates/` (requirements, architecture, wireframes, estimates, jira-comments, reports, migration-plans, testing).
- Frontmatter (schemas/report.schema.json): `title, kind, ticket, execution, odoo_version, generated_at, verification_levels`.
- Location: `.odoo-master/{plans,reports,architecture,migration,estimates}/<ticket-or-slug>/`.
- Render: `odoo-master report <file.md> --formats html,pdf` → verifies the PDF (page count) and writes outputs next to the source; Mermaid blocks render when the browser can load mermaid, otherwise they are shown as code.
- Honesty: every report lists verification levels achieved and missing (`odoo-master evidence manifest -e <id>`), unresolved issues and assumptions.
- No secrets, no production personal data.
