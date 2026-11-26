---
name: odoo-model-development
description: "Odoo ORM modelling: new models, extending standard models, fields and parameters, computed/related/stored fields, constraints and indexes per version, onchange, CRUD overrides with super(), multi-company, mail.thread/activity mixins, and batching. Use when adding or changing Python models."
---

# Odoo model development

## Patterns
```python
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class StockPicking(models.Model):
    _inherit = "stock.picking"                     # extension: same table

    quality_state = fields.Selection(
        [("none", "No checks"), ("todo", "Pending"), ("done", "Done")],
        compute="_compute_quality_state", store=True, index=True,
    )

    @api.depends("quality_check_ids.state")        # every dependency path listed
    def _compute_quality_state(self):
        for picking in self:                        # assign for every record
            states = picking.quality_check_ids.mapped("state")
            picking.quality_state = "none" if not states else "todo" if "todo" in states else "done"

    def button_validate(self):
        if any(p.quality_state == "todo" for p in self):
            raise UserError(self.env._("Complete the quality checks first."))   # env._ on 18+, _() before
        return super().button_validate()            # ALWAYS call super()


class QualityCheck(models.Model):
    _name = "stock.quality.check"
    _description = "Quality Check"
    _inherit = ["mail.thread"]                     # mixins: _name + _inherit list
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda s: s.env.company)
    picking_id = fields.Many2one("stock.picking", required=True, ondelete="cascade", index=True, check_company=True)

    # 19.0+ (ignored silently on 19 if written as _sql_constraints!)
    _name_company_uniq = models.Constraint("UNIQUE(name, company_id)", "Name must be unique per company.")
    # ≤18.0 equivalent:
    # _sql_constraints = [("name_company_uniq", "unique(name, company_id)", "Name must be unique per company.")]

    @api.constrains("name")
    def _check_name(self):
        for rec in self:
            if rec.name and len(rec.name) < 3:
                raise ValidationError("Name too short")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("name", self.env["ir.sequence"].next_by_code("stock.quality.check") or "/")
        return super().create(vals_list)
```
## Rules
- Stored computed fields on large tables: consider recompute cost and an upgrade script.
- Renaming/retyping a stored field loses data unless a `migrations/<ver>/pre-*.py` script handles it (see `odoo-migration`).
- `display_name` via `_compute_display_name` (not `name_get`, deprecated 16.4+).
- `group_operator=` → `aggregator=` (18+). `self._cr/_uid/_context` → `self.env.cr/uid/context` (19+).
- Access checks: `check_access('write')` (18+) instead of `check_access_rights` + `check_access_rule`.
- Search in loops is a bug: batch with `read_group`/`_read_group`, `mapped`, `filtered`, `search_fetch` (16.2+).
- New model ⇒ ACL rows (see `odoo-security`).
