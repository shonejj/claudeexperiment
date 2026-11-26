from odoo_master.odoo.inventory import scan
from odoo_master.project import analyze


def test_inventory_models_views_security(fx):
    inv = scan(fx("odoo18_project"), series="18.0")
    m = inv["modules"]["stock_quality_check"]
    names = {x["name"]: x for x in m["models"]}
    assert names["stock.quality.check"]["kind"] == "new"
    assert names["stock.picking"]["kind"] == "extension"
    meth = {x["name"]: x for x in names["stock.picking"]["methods"]}
    assert meth["button_validate"]["calls_super"] is True
    assert {v["inherit_id"] for v in m["views"]} >= {"stock.view_picking_form"}
    assert m["acl_format"] == "ir.model.access" and len(m["acl"]) == 2
    assert m["tests"]["python"] == 1
    assert inv["findings"]["models_missing_acl"] == []
    arch = inv["architecture"]["models"]["stock.picking"]
    assert arch["standard_model_extended"] and arch["standard_defined_in"] == "stock"


def test_missing_acl_and_dependency_map(fx):
    inv = scan(fx("broken_module"), series="18.0")
    assert any(f["model"] == "broken.thing" for f in inv["findings"]["models_missing_acl"])
    assert inv["dependencies"]["graph"]["broken_mod"] == ["sale"]
    assert inv["dependencies"]["unknown_dependencies"] == {}


def test_dependency_cycle_detection(tmp_path):
    for a, b in (("mod_a", "mod_b"), ("mod_b", "mod_a")):
        (tmp_path / a).mkdir()
        (tmp_path / a / "__manifest__.py").write_text(f"{{'name': '{a}', 'depends': ['{b}']}}")
    inv = scan(tmp_path)
    assert inv["dependencies"]["cycles"] == [["mod_a", "mod_b"]]


def test_analyze_writes_knowledge_files(fx):
    root = fx("odoo16_legacy")
    res = analyze(root)
    sd = root / ".odoo-master"
    for f in ("project-inventory.json", "architecture-map.json", "module-dependency-map.json", "odoo-version.json", "project-context.md"):
        assert (sd / f).exists(), f
    assert res["project"]["odoo"]["version"] == "16.0"
    assert any("Code-level analysis only" in k for k in res["project"]["knowledge_limits"])
    ctx = (sd / "project-context.md").read_text()
    assert "sale.order" in ctx and "standard: `sale`" in ctx
