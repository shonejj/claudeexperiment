from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestQualityCheck(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.picking_type = cls.env.ref("stock.picking_type_in")
        cls.picking = cls.env["stock.picking"].create({
            "picking_type_id": cls.picking_type.id,
            "location_id": cls.env.ref("stock.stock_location_suppliers").id,
            "location_dest_id": cls.env.ref("stock.stock_location_stock").id,
        })

    def test_quality_state(self):
        self.assertEqual(self.picking.quality_state, "none")
        check = self.env["stock.quality.check"].create({"picking_id": self.picking.id})
        self.assertEqual(self.picking.quality_state, "todo")
        check.action_pass()
        self.assertEqual(self.picking.quality_state, "done")

    def test_validate_blocked(self):
        self.env["stock.quality.check"].create({"picking_id": self.picking.id})
        with self.assertRaises(UserError):
            self.picking.button_validate()
