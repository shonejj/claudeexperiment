---
name: wireframing
description: "Lightweight wireframes for Odoo screens and flows (Mermaid flows, ASCII form layouts, or an HTML mock) that map directly to view XML anchors. Use when a feature adds or reshapes UI and the layout needs agreement before coding."
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

# Wireframing

- Flow: Mermaid `flowchart` or `sequenceDiagram` of the user journey (menu → list → form → action).
- Form layout (ASCII), annotated with the base view and anchor:
```
[Header: Pass | Fail | statusbar(state)]           (new view)
| Name      [_____]   | Picking [WH/IN/0007 v] |
| Note      [_________________________________] |
Notebook > Quality (page added inside //notebook of stock.view_picking_form)
```
- For richer mocks write a static HTML file using Odoo-like structure (o_form_view, o_group) — clearly labelled as a mock.
- Save to `.odoo-master/architecture/wireframes/<slug>.md`; reference from the technical plan.
