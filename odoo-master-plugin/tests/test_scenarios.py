"""End-to-end scenario tests through the real CLI (no LLM): the deterministic backbone of
acceptance scenarios A, C, E and F. The LLM-driven parts are covered by evals/ (claude plugin eval)."""
import hashlib
import hmac
import json

from conftest import FIXTURES, cli


def test_scenario_a_existing_repo_analysis_plan_estimate_pdf(fx, tmp_path):
    root = fx("odoo18_project")
    rc, out, _ = cli("analyze", "--brief", root=root)
    assert rc == 0 and out.startswith("18.0 (high)")
    rc, c, _ = cli("classify", "Analyze this project and identify how to implement a custom inventory module", root=root)
    assert c["odoo_project"] and "inventory" in c["apps"]
    rc, ex, _ = cli("workflow", "start", "new-odoo-module", "-i", "request=inventory quality per lot", root=root)
    eid = ex["execution"]
    for step, output in (("intake", {"odoo_version": "18.0"}), ("requirements", {"risk": "medium"}),
                         ("reuse-check", {"decision": "extend", "target_module": "stock_quality_check"}), ("design", {}), ("estimate", {})):
        f = tmp_path / f"{step}.json"
        f.write_text(json.dumps(output))
        rc, r, _ = cli("workflow", "complete", "-e", eid, "--step", step, "--status", "DONE", "--output", str(f), root=root)
    assert r["status"] == "waiting_approval" and r["waiting_approval"][0]["step"] == "plan-approval"   # approval requested
    est_in = tmp_path / "est.json"
    est_in.write_text(json.dumps({"tasks": [{"id": "T1", "title": "lot checks", "kind": "model", "complexity": "moderate"}]}))
    rc, est, _ = cli("estimate", "--input", str(est_in), "--out", str(root / ".odoo-master/estimates/plan"), root=root)
    assert est["total_hours"] > 0 and (root / ".odoo-master/estimates/plan.md").exists()
    plan = root / ".odoo-master/plans/plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("---\ntitle: Plan\nkind: implementation-plan\n---\n# Plan\n\n" + (root / ".odoo-master/estimates/plan.md").read_text())
    rc, rep, _ = cli("report", str(plan), "--formats", "html,pdf", root=root)
    pdf = [o for o in rep["outputs"] if o["format"] == "pdf"][0]
    assert pdf["ok"] or pdf["engine"] is None


def test_scenario_c_event_to_execution_to_evidence(fx, tmp_path, monkeypatch):
    root = fx("odoo18_project")
    monkeypatch.setenv("ODOO_MASTER_JIRA_WEBHOOK_SECRET", "k")
    body = (FIXTURES / "events/jira_labeled.json").read_bytes()
    sig = "sha256=" + hmac.new(b"k", body, hashlib.sha256).hexdigest()
    payload = tmp_path / "p.json"
    payload.write_bytes(body)
    rc, r, _ = cli("events", "simulate", "--source", "jira", "--payload", str(payload), "--header", f"X-Hub-Signature={sig}", root=root)
    assert r["results"][0]["workflow"] == "jira-ticket-planning"
    rc, recs, _ = cli("events", "executions", root=root)
    ticket = recs[0]["inputs"]["ticket"]
    assert ticket == "INV-42"
    # the headless run would start the workflow from the record:
    rc, ex, _ = cli("workflow", "start", recs[0]["workflow"], "-i", f"ticket={ticket}", "--ticket", ticket, root=root)
    eid = ex["execution"]
    assert ex["ticket"] == "INV-42" and ex["ready"][0]["capability"] is None and ex["ready"][0]["step"] == "capabilities"
    tools = tmp_path / "tools.json"
    tools.write_text(json.dumps([{"name": "mcp__atlassian__getJiraIssue"}, {"name": "mcp__atlassian__addCommentToJiraIssue"},
                                 {"name": "mcp__atlassian__searchJiraIssuesUsingJql"}]))
    cli("mcp", "register", "--tools", str(tools), root=root)
    rc, res, _ = cli("mcp", "resolve", "ticket.add_comment", root=root)
    assert res["tools"][0]["qualified_name"] == "mcp__atlassian__addCommentToJiraIssue"
    for step in ("capabilities", "read-ticket", "analyse-repo", "actionability", "technical-plan"):
        rc, r, _ = cli("workflow", "complete", "-e", eid, "--step", step, "--status", "DONE", root=root)
    assert r["waiting_approval"][0]["step"] == "post-approval"
    rc, r, _ = cli("workflow", "approve", "-e", eid, "--step", "post-approval", "--by", "Dana via INV-42 comment", root=root)
    assert r["ready"][0]["step"] == "post-plan" and r["ready"][0]["capability"] == "ticket.add_comment"
    v = tmp_path / "validation.json"
    rc, val, _ = cli("validate", "--brief", root=root)
    v.write_text(val)
    cli("evidence", "add", "-e", eid, "--kind", "validation", "--level", "static", "--path", str(v), "--status", "passed", root=root)
    rc, r, _ = cli("workflow", "complete", "-e", eid, "--step", "post-plan", "--status", "DONE", root=root)
    assert r["status"] == "completed"
    rc, m, _ = cli("evidence", "manifest", "-e", eid, root=root)
    assert m["ticket"] == "INV-42" and m["levels_achieved"] == ["static"]


def test_scenario_e_migration_plan(fx):
    root = fx("odoo16_legacy")
    rc, plan, _ = cli("migration", "plan", "--from", "16.0", "--to", "19.0", root=root)
    assert plan["plan"]["hops"] == ["17.0", "18.0", "19.0"] and plan["scan_totals"]["blockers"] >= 5
    rc, v, _ = cli("validate", "--series", "19.0", root=root)
    assert rc == 1 and not v["passed"]          # code is not yet valid for 19.0


def test_scenario_f_new_mcp_server_discovery(fx):
    root = fx("odoo19_project")
    (root / ".mcp.json").write_text(json.dumps({"mcpServers": {"odoo-copy": {"type": "stdio", "command": "python3",
        "args": ["-m", "odoo_master.mcp.server"], "env": {"PYTHONPATH": str(FIXTURES.parents[1] / "scripts")}}}}))
    rc, s, _ = cli("mcp", "servers", root=root)
    assert "odoo-copy" in s["servers"]
    rc, p, _ = cli("mcp", "probe", "--names", "odoo-copy", root=root)
    assert p["probed"]["odoo-copy"]["status"] == "connected" and p["probed"]["odoo-copy"]["tools"] == 6
    rc, r, _ = cli("mcp", "resolve", "odoo.analyze", root=root)
    assert {t["server"] for t in r["tools"]} == {"odoo-copy"} and all(t["access"] == "read" for t in r["tools"])
    rc, r, _ = cli("mcp", "resolve", "ticket.transition", root=root)
    assert rc == 1 and r["tools"] == []        # unsupported capability handled gracefully
