{
    "name": "Stock Quality Check",
    "version": "18.0.1.0.0",
    "summary": "Simple quality checks on incoming pickings",
    "license": "LGPL-3",
    "depends": ["stock"],
    "data": [
        "security/ir.model.access.csv",
        "views/quality_check_views.xml",
        "views/stock_picking_views.xml",
    ],
    "installable": True,
}
