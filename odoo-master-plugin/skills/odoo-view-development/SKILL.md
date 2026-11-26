---
name: odoo-view-development
description: "Odoo XML views and UI data: form/list/kanban/search views, XPath inheritance and positions, version-correct syntax (no attrs on 17+, list on 18+), actions, menus, and avoiding view duplication. Use when adding or changing views, actions or menus."
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

# Odoo view development

## Inherit, never copy
```xml
<record id="view_picking_form_quality" model="ir.ui.view">
    <field name="name">stock.picking.form.quality</field>
    <field name="model">stock.picking</field>
    <field name="inherit_id" ref="stock.view_picking_form"/>
    <field name="arch" type="xml">
        <xpath expr="//field[@name='origin']" position="after">
            <field name="quality_state" invisible="quality_state == 'none'"/>   <!-- 17+ expression -->
        </xpath>
        <xpath expr="//notebook" position="inside">
            <page string="Quality" name="quality">
                <field name="quality_check_ids"/>
            </page>
        </xpath>
    </field>
</record>
```
- Positions: `inside`, `after`, `before`, `replace` (avoid on standard views), `attributes` (`<attribute name="invisible">...</attribute>`), `move`.
- Shorthand `<field name="x" position="after">` works; XPath with stable anchors (`@name`) is more robust than indexes.
- 16.0: `attrs="{'invisible': [('state','=','draft')]}"`, `states="..."`. **17.0+**: `invisible="state == 'draft'"`, `readonly=`, `required=`, `column_invisible=` in lists. Python-like expressions over field values (and `context`, `uid`, `parent.` in one2many sub-views).
- **18.0+**: `<list>` instead of `<tree>`, `view_mode="list,form"`, `ir.actions.act_window.view` with `view_mode` list.
- 19.0+: menus/views/actions use `group_ids` field (XML attribute `groups="module.group"` still works on elements).
- Find the base view and its anchors in the standard source of the exact series (no clone):
  `odoo-master source grep 'id="view_picking_form"' --module stock --series 18.0` → then
  `odoo-master source show addons/stock/views/stock_picking_views.xml --start 110 --end 200 --plain --series 18.0`
- Every `ref`/`groups` must point to a module in the transitive dependencies (validator rule `xml-ref-module-not-in-depends`).
- After changes: `odoo-master validate --files <xml>`; runtime install catches XPath target errors (static analysis cannot see standard views).
