# Documentation standards

- Every deliverable starts from a template in `templates/` and carries frontmatter per `schemas/report.schema.json`.
- Plans/reports live in `.odoo-master/{plans,reports,architecture,migration,estimates}/<ticket-or-slug>/`.
- Write for a reviewer: decisions with reasons, evidence links, assumptions, open questions.
- Diagrams in Mermaid. Estimates are effort ranges with assumptions, never promises.
- Render with `odoo-master report <md> --formats html,pdf`; the renderer verifies the PDF.
- Redact secrets; summarise rather than paste large logs (use `odoo-master logs summarize`).
