---
name: architecture-planning
description: "Technical design and implementation planning for Odoo and general software: customisation strategy, module/model/view/security design, module impact and database impact analysis, migration considerations, Mermaid diagrams, work breakdown with verification per task. Use after requirements and before implementation."
---


# Architecture planning

Templates: `${CLAUDE_PLUGIN_ROOT}/templates/architecture/technical-plan.md`, `templates/architecture/module-impact.md`.

1. **Strategy** (reuse ladder rung + rationale + alternatives rejected).
2. **Module impact**: modules touched/created, `depends` changes, reverse dependencies affected (`module-dependency-map.json` → `reverse`).
3. **Data model**: models/fields (type, stored?, indexed?, compute deps), constraints (version-correct), ACL per group, record rules.
4. **UI**: views to inherit (exact ids + anchors), new actions/menus; wireframe if non-trivial.
5. **Database impact**: new tables/columns, renamed/removed stored fields (→ upgrade scripts), data backfills, expected volumes.
6. **Migration considerations**: manifest version bump, scripts, compatibility with the next Odoo series.
7. **Integrations & security**.
8. **Implementation steps**: ordered tasks, each with files and the verification command.
9. **Test plan**: unit/HttpCase/tour per acceptance criterion; runtime levels.
10. **Risks** with mitigations. Diagram:
```mermaid
flowchart LR
  A[stock.picking validate] -->|checks pending?| B{quality_state}
  B -->|todo| C[UserError]
  B -->|done/none| D[super().button_validate]
```
