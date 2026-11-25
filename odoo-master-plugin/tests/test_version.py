import pytest

from odoo_master.odoo.version import detect, brief


@pytest.mark.parametrize("name,expected", [("odoo16_legacy", "16.0"), ("odoo17_project", "17.0"), ("odoo18_project", "18.0"),
                                           ("odoo19_project", "19.0"), ("odoo20_project", "20.0")])
def test_detects_series(fx, name, expected):
    res = detect(fx(name))
    assert res["version"] == expected
    assert res["confidence"] == "high"
    assert not res["conflicts"]
    assert res["signals"], "evidence must be returned"


def test_conflicting_syntax_lowers_confidence(fx):
    res = detect(fx("broken_module"))          # manifest says 18.0 but views use attrs (<17)
    assert res["version"] == "18.0"
    assert res["confidence"] != "high"
    assert any(c["type"] == "syntax_contradicts_declared_version" for c in res["conflicts"])
    assert "CONFLICTS" in brief(res)


def test_release_py_wins(fx):
    root = fx("odoo18_project")
    (root / "odoo").mkdir()
    (root / "odoo" / "release.py").write_text("version_info = (19, 0, 0, 'final', 0, '')\n")
    res = detect(root)
    assert res["version"] == "19.0"
    assert any(c["type"] == "strong_signals_disagree" for c in res["conflicts"])


def test_fingerprints_only(tmp_path):
    mod = tmp_path / "m"
    (mod / "views").mkdir(parents=True)
    (mod / "__manifest__.py").write_text("{'name': 'm'}")
    (mod / "views" / "v.xml").write_text("<odoo><record id='a' model='ir.ui.view'><field name='arch' type='xml'><list/></field></record></odoo>")
    (mod / "security").mkdir()
    (mod / "security" / "ir.access.csv").write_text("id,name,model_id,group_id/id,operation,domain\n")
    res = detect(tmp_path)
    assert res["version"] == "20.0"
    assert res["confidence"] == "low"
