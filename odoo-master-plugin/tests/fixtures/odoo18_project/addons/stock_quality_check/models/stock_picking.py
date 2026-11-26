from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    quality_check_ids = fields.One2many("stock.quality.check", "picking_id")
    quality_state = fields.Selection(
        [("none", "No checks"), ("todo", "Pending"), ("done", "Done")],
        compute="_compute_quality_state", store=True,
    )

    @api.depends("quality_check_ids.state")
    def _compute_quality_state(self):
        for picking in self:
            states = picking.quality_check_ids.mapped("state")
            picking.quality_state = "none" if not states else "todo" if "todo" in states else "done"

    def button_validate(self):
        if any(p.quality_state == "todo" for p in self):
            from odoo.exceptions import UserError
            raise UserError("Complete the quality checks first.")
        return super().button_validate()
