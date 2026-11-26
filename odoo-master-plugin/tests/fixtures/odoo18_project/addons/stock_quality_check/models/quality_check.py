from odoo import api, fields, models


class StockQualityCheck(models.Model):
    _name = "stock.quality.check"
    _description = "Stock Quality Check"
    _order = "id desc"

    name = fields.Char(required=True, default="New")
    picking_id = fields.Many2one("stock.picking", required=True, ondelete="cascade", index=True)
    state = fields.Selection([("todo", "To Do"), ("pass", "Passed"), ("fail", "Failed")], default="todo", required=True)
    note = fields.Text()
    result_count = fields.Integer(compute="_compute_result_count")

    @api.depends("state")
    def _compute_result_count(self):
        for rec in self:
            rec.result_count = 1 if rec.state != "todo" else 0

    def action_pass(self):
        self.write({"state": "pass"})

    def action_fail(self):
        self.write({"state": "fail"})
