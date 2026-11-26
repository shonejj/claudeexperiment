---
name: requirements-analysis
description: "Turning a request, ticket or chat report into testable requirements for Odoo work: goals, user stories, business rules, acceptance criteria, non-functional needs, open questions, actionability verdict, and mapping to Odoo apps/models. Use at the start of feature, ticket or change-request work."
---

# Requirements analysis

Use `${CLAUDE_PLUGIN_ROOT}/templates/requirements/requirements.md`.

1. **Context**: who is asking, which Odoo apps/flows (Sales, Inventory, Accounting...), which company/multi-company constraints.
2. **Current behaviour**: what standard Odoo and existing custom modules already do (cite inventory / standard model map). Many requests are configuration.
3. **Requirements**: user stories + business rules; distinguish must / should / later.
4. **Acceptance criteria**: verifiable statements; each will map to a test or a manual check.
5. **Non-functional**: volumes, performance, security/roles, audit (tracking), localisation, multi-company, reporting.
6. **Data**: new data, migrated data, imports.
7. **Open questions** with a proposed default for each; **actionable?** yes/no with reason.
8. **Risk** low/medium/high/critical (data loss, accounting impact, production, many users).
Write to `.odoo-master/plans/<ticket-or-slug>/requirements.md`.
