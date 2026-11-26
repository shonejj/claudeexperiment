from odoo_master.planning.classify import classify
from odoo_master.planning.estimate import estimate, to_markdown
from odoo_master.project import analyze

import pytest


def test_classify_signals(fx):
    root = fx("odoo18_project")
    analyze(root)
    c = classify("Fix the error when validating receipts in stock_quality_check (stock.picking), ticket INV-42", root)
    assert c["candidates"][0]["intent"] == "bug_fix" and c["candidates"][0]["workflow"] == "bug-fix"
    assert c["existing_modules_mentioned"] == ["stock_quality_check"]
    assert "stock.picking" in c["models_mentioned"] and "inventory" in c["apps"] and c["references"]["tickets"] == ["INV-42"]
    m = classify("Migrate our modules from Odoo 16 to 18", root)
    assert m["candidates"][0]["intent"] == "migration" and m["versions_mentioned"] == ["16.0", "18.0"] and m["risk_hint"] == "high"
    n = classify("Build a new module for fleet fuel cards", root)
    assert n["candidates"][0]["intent"] == "new_module"


def test_estimate():
    est = estimate({"confidence": "high", "tasks": [
        {"id": "T1", "title": "model", "kind": "model", "complexity": "moderate", "new_module": True},
        {"id": "T2", "title": "view", "kind": "view", "complexity": "simple", "unknowns": 2}]})
    assert est["tasks"][0]["hours"] == pytest.approx(6.9)
    assert est["tasks"][1]["hours"] == pytest.approx(2.6)
    assert est["total_hours"] == pytest.approx(round((6.9 + 2.6) * 1.45, 1), abs=0.11)
    assert est["range_hours"][0] < est["total_hours"] < est["range_hours"][1]
    assert "not a delivery commitment" in to_markdown(est)
    with pytest.raises(ValueError):
        estimate({"tasks": [{"id": "x", "title": "y", "kind": "bogus", "complexity": "simple"}]})
