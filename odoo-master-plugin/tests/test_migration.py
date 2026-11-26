import pytest

from odoo_master.odoo.migration import hops, plan_skeleton, scan


def test_hops():
    assert hops("16.0", "19.0") == ["17.0", "18.0", "19.0"]
    assert hops("18.0", "20.0") == ["19.0", "20.0"]


def test_scan_16_to_20(fx):
    res = scan(fx("odoo16_legacy"), "16.0", "20.0")
    found = {(f["rule"], f["since"]) for m in res["modules"].values() for f in m["findings"]}
    expected = {("attrs-states-removed", "17.0"), ("init-hook-env", "17.0"), ("name-get-deprecated", "17.0"),
                ("tree-to-list", "18.0"), ("group-operator-renamed", "18.0"), ("check-access-rights-split", "18.0"),
                ("sql-constraints-unsupported", "19.0"), ("users-groups-id-renamed", "19.0"), ("osv-deprecated", "19.0"),
                ("acl-csv-replaced", "20.0"), ("ir-rule-removed", "20.0")}
    assert expected <= found, expected - found
    assert res["totals"]["blockers"] >= 7
    plan = plan_skeleton(res)
    assert [s["hop"] for s in plan["steps"]] == ["17.0", "18.0", "19.0", "20.0"]
    assert plan["rollback"] and plan["validation"]


def test_scan_rejects_downgrade(fx):
    with pytest.raises(ValueError):
        scan(fx("odoo18_project"), "18.0", "17.0")


def test_scan_18_to_19_only_relevant_rules(fx):
    res = scan(fx("odoo16_legacy"), "18.0", "19.0")
    sinces = {f["since"] for m in res["modules"].values() for f in m["findings"]}
    assert sinces == {"19.0"}
