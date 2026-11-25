import datetime as dt
import json

import pytest

from odoo_master.util import read_json, write_json
from odoo_master.workflow import engine
from odoo_master.workflow.expr import evaluate


def test_all_shipped_workflows_valid():
    res = engine.validate_all()
    assert len(res) >= 15
    assert all(v["valid"] for v in res.values()), {k: v["errors"] for k, v in res.items() if not v["valid"]}


def test_expression_sandbox():
    assert evaluate("ctx.get('risk') == 'low'", ctx={"risk": "low"}, inputs={}, config={})
    assert evaluate("inputs.get('ticket')", ctx={}, inputs={"ticket": "A-1"}, config={})
    for bad in ("__import__('os').system('x')", "ctx.__class__", "open('f')", "[x for x in ctx]", "lambda: 1"):
        with pytest.raises(ValueError):
            evaluate(bad, ctx={}, inputs={}, config={})


def _project_with_workflow(tmp_path, wf: str):
    d = tmp_path / ".odoo-master" / "workflows"
    d.mkdir(parents=True)
    (d / "t.yaml").write_text(wf)
    return tmp_path


WF = """
schema_version: 1
name: t
version: 1.0.0
description: test
inputs: {request: {required: true}}
steps:
  - {id: a, agent: project-analyst}
  - {id: b1, agent: code-reviewer, needs: [a], parallel_group: g}
  - {id: b2, agent: qa-engineer, needs: [a], parallel_group: g}
  - {id: skip-me, agent: qa-engineer, needs: [a], when: "ctx.get('never')"}
  - {id: gate, type: approval, needs: [b1, b2]}
  - {id: impl, agent: odoo-developer, needs: [gate]}
  - {id: test, agent: qa-engineer, needs: [impl], on_failure: {retry_from: impl, max_loops: 2}}
"""


def test_parallel_skip_gate_and_repair_loop(tmp_path):
    root = _project_with_workflow(tmp_path, WF)
    with pytest.raises(ValueError):
        engine.start("t", {}, root)                         # required input
    r = engine.start("t", {"request": "x"}, root)
    eid = r["execution"]
    assert [s["step"] for s in r["ready"]] == ["a"]
    r = engine.complete(eid, "a", "DONE", {"risk": "medium"}, root)
    assert {s["step"] for s in r["ready"]} == {"b1", "b2"}  # parallel
    assert r["progress"]["skip-me"] == "SKIPPED"
    engine.complete(eid, "b1", "DONE", {}, root)
    r = engine.complete(eid, "b2", "DONE", {}, root)
    assert r["status"] == "waiting_approval" and r["waiting_approval"][0]["step"] == "gate"
    with pytest.raises(ValueError):
        engine.approve(eid, "gate", "", root)               # approver identity required
    r = engine.approve(eid, "gate", "Dana (in session)", root)
    assert [s["step"] for s in r["ready"]] == ["impl"]
    # repair loop: test fails twice -> impl re-run; third failure exhausts max_loops
    for loop in range(2):
        r = engine.complete(eid, "impl", "DONE", {}, root)
        assert [s["step"] for s in r["ready"]] == ["test"]
        r = engine.complete(eid, "test", "FAILED", {"error": "boom"}, root, note="tests failed")
        assert [s["step"] for s in r["ready"]] == ["impl"], loop
    r = engine.complete(eid, "impl", "DONE", {}, root)
    r = engine.complete(eid, "test", "FAILED", {}, root)
    assert r["status"] == "failed"
    ex = read_json(root / ".odoo-master" / "executions" / f"{eid}.json")
    assert ex["approvals"][0]["by"] == "Dana (in session)"
    events = (root / ".odoo-master" / "executions" / f"{eid}.events.jsonl").read_text().splitlines()
    assert any(json.loads(e)["type"] == "approval" for e in events)


def test_autonomous_auto_approves_only_low_risk(tmp_path, monkeypatch):
    root = _project_with_workflow(tmp_path, WF)
    monkeypatch.setenv("ODOO_MASTER_AUTONOMY", "autonomous")
    eid = engine.start("t", {"request": "x"}, root)["execution"]
    engine.complete(eid, "a", "DONE", {"risk": "low"}, root)
    engine.complete(eid, "b1", "DONE", {}, root)
    r = engine.complete(eid, "b2", "DONE", {}, root)
    assert r["progress"]["gate"] == "APPROVED"
    eid2 = engine.start("t", {"request": "y"}, root)["execution"]
    engine.complete(eid2, "a", "DONE", {"risk": "high"}, root)
    engine.complete(eid2, "b1", "DONE", {}, root)
    r = engine.complete(eid2, "b2", "DONE", {}, root)
    assert r["status"] == "waiting_approval"


def test_timeout_blocked_resume_cancel(tmp_path):
    wf = WF.replace("- {id: a, agent: project-analyst}", "- {id: a, agent: project-analyst, timeout_minutes: 1, retries: 0}")
    root = _project_with_workflow(tmp_path, wf)
    eid = engine.start("t", {"request": "x"}, root)["execution"]
    p = root / ".odoo-master" / "executions" / f"{eid}.json"
    ex = read_json(p)
    ex["steps"]["a"]["deadline"] = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)).isoformat()
    write_json(p, ex)
    r = engine.next_steps(eid, root)
    assert r["progress"]["a"] == "TIMED_OUT" and r["status"] == "failed"
    eid = engine.start("t", {"request": "x"}, root)["execution"]
    r = engine.complete(eid, "a", "BLOCKED", {}, root, note="no database access")
    assert r["status"] == "blocked"
    engine.set_context(eid, {"db": "authorised"}, root)
    r = engine.next_steps(eid, root)                     # resume: step re-dispatched
    assert [s["step"] for s in r["ready"]] == ["a"]
    assert engine.cancel(eid, root)["status"] == "cancelled"
    assert any(e["id"] == eid and e["status"] == "cancelled" for e in engine.list_executions(root))


def test_rejection_loops_back(tmp_path):
    wf = WF.replace("- {id: gate, type: approval, needs: [b1, b2]}", "- {id: gate, type: approval, needs: [b1, b2], on_reject: a}")
    root = _project_with_workflow(tmp_path, wf)
    eid = engine.start("t", {"request": "x"}, root)["execution"]
    for s in ("a", "b1", "b2"):
        engine.complete(eid, s, "DONE", {}, root)
    r = engine.approve(eid, "gate", "Lead", root, decision="rejected", note="use existing module")
    assert [s["step"] for s in r["ready"]] == ["a"]
    assert engine.status(eid, root)["approvals"][0]["decision"] == "rejected"
