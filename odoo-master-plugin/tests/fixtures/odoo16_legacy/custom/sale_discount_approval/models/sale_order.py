from odoo import api, fields, models
from odoo.osv import expression


class SaleOrder(models.Model):
    _inherit = "sale.order"

    discount_approved = fields.Boolean(group_operator="bool_and")
    approval_ref = fields.Char()

    _sql_constraints = [
        ("approval_ref_uniq", "unique(approval_ref)", "Approval reference must be unique."),
    ]

    def name_get(self):
        return [(o.id, "%s (%s)" % (o.name, o.partner_id.name)) for o in self]

    def action_confirm(self):
        self.check_access_rights("write")
        return super().action_confirm()


class DiscountRequest(models.Model):
    _name = "sale.discount.request"
    _description = "Discount Request"

    order_id = fields.Many2one("sale.order", required=True)
    user_ids = fields.Many2many("res.users")

    def _get_managers(self):
        return self.env["res.users"].search([("groups_id", "in", self.env.ref("sales_team.group_sale_manager").id)])
