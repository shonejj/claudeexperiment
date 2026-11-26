from odoo import api, fields, models


class BrokenThing(models.Model):
    _name = "broken.thing"
    _description = "Broken thing"

    name = fields.Char()

    @api.multi
    def do_it(self, term):
        self.env.cr.execute("SELECT id FROM broken_thing WHERE name = '%s'" % term)
        return eval(term)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def write(self, vals):
        return True
