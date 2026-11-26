def post_init_hook(cr, registry):
    cr.execute("UPDATE sale_order SET discount_approved = true WHERE state = 'sale'")
