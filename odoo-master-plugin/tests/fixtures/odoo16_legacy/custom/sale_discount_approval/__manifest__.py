{
    "name": "Sale Discount Approval",
    "version": "16.0.1.2.0",
    "license": "LGPL-3",
    "depends": ["sale_management"],
    "data": ["security/ir.model.access.csv", "security/discount_security.xml", "views/sale_order_views.xml"],
    "post_init_hook": "post_init_hook",
}
