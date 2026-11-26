from odoo import api, fields, models


class PurchaseBudget(models.Model):
    _name = "purchase.budget"
    _description = "Purchase Budget"

    name = fields.Char(required=True)
    amount = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)
    state = fields.Selection([("draft", "Draft"), ("open", "Open")], default="draft")

    _sql_constraints = [("name_uniq", "unique(name)", "Budget name must be unique.")]
