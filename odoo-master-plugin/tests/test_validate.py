from odoo_master.odoo.validate import validate


def rules(res):
    return {f["rule"] for f in res["findings"] if f["severity"] == "error"}


def test_healthy_fixtures_pass(fx):
    for name, series in (("odoo16_legacy", "16.0"), ("odoo17_project", "17.0"), ("odoo18_project", "18.0"),
                         ("odoo19_project", "19.0"), ("odoo20_project", "20.0")):
        res = validate(fx(name), series=series, with_js=False)
        assert res["passed"], (name, [f for f in res["findings"] if f["severity"] == "error"])


def test_broken_module_findings(fx):
    res = validate(fx("broken_module"), series="18.0", with_js=False)
    assert not res["passed"]
    assert {"manifest-license", "manifest-data-missing", "xml-parse", "py-sql-injection", "py-removed-api-decorator",
            "py-override-no-super", "py-eval", "acl-missing-model", "attrs-states-removed"} <= rules(res)
    assert any(f["rule"] == "data-file-unlisted" for f in res["findings"])
    for f in res["findings"]:
        assert f["file"] and f["message"]


def test_xpath_and_dependency_refs(fx):
    root = fx("odoo18_project")
    v = root / "addons/stock_quality_check/views/extra.xml"
    v.write_text('''<odoo>
  <record id="x" model="ir.ui.view"><field name="model">stock.picking</field>
    <field name="inherit_id" ref="stock.view_picking_form"/>
    <field name="arch" type="xml"><xpath expr="//field[@name='origin']" position="sideways"><field name="note"/></xpath></field></record>
  <menuitem id="m" action="crm.crm_lead_action"/>
</odoo>''')
    mf = root / "addons/stock_quality_check/__manifest__.py"
    mf.write_text(mf.read_text().replace('"views/stock_picking_views.xml",', '"views/stock_picking_views.xml",\n        "views/extra.xml",'))
    res = validate(root, series="18.0", with_js=False)
    r = rules(res)
    assert "xml-view-target" in r
    assert "xml-ref-module-not-in-depends" in r       # crm not a (transitive) dependency of stock


def test_transitive_dependencies_accepted(fx):
    # sale_management -> sale -> sales_team: refs to sale.* and sales_team.* are valid
    res = validate(fx("odoo16_legacy"), series="16.0", with_js=False)
    assert "xml-ref-module-not-in-depends" not in rules(res)
    assert "acl-group-ref" not in rules(res)


def test_version_rules_apply_to_target(fx):
    res = validate(fx("odoo16_legacy"), series="19.0", with_js=False)
    r = rules(res)
    assert {"attrs-states-removed", "tree-to-list", "sql-constraints-unsupported", "users-groups-id-renamed", "init-hook-env"} <= r


def test_odoo20_acl_header(fx):
    root = fx("odoo20_project")
    p = root / "addons/project_risk/security/ir.access.csv"
    p.write_text("id,name,model_id:id,group_id:id,perm_read\nx,y,z,,1\n")
    res = validate(root, series="20.0", with_js=False)
    assert "acl-header" in rules(res)


def test_js_syntax_check(fx):
    import shutil
    if not shutil.which("node"):
        return
    root = fx("odoo18_project")
    js = root / "addons/stock_quality_check/static/src/bad.js"
    js.parent.mkdir(parents=True)
    js.write_text("export function x( {\n")
    res = validate(root, series="18.0", with_js=True)
    assert "js-syntax" in rules(res)


def test_attrs_via_attribute_element_detected(fx):
    root = fx("odoo18_project")
    v = root / "addons/stock_quality_check/views/legacy.xml"
    v.write_text('<odoo><record id="lv" model="ir.ui.view"><field name="model">stock.quality.check</field>'
                 '<field name="inherit_id" ref="stock_quality_check.stock_quality_check_view_form"/><field name="arch" type="xml">'
                 '<field name="note" position="attributes"><attribute name="attrs">{\'invisible\': True}</attribute></field>'
                 '</field></record></odoo>')
    res = validate(root, series="18.0", with_js=False)
    assert any(f["rule"] == "attrs-states-removed" and f["file"].endswith("legacy.xml") for f in res["findings"])
