"""Tests for 0.2.0 features: scaffold, lookup, doctor, init, status, watch, soft CLI, new hooks,
plugin components (commands, output style, monitors, LSP, userConfig), HTTP event receiver, Linear."""
import hashlib
import hmac
import json
import socket
import subprocess
import sys
import threading
import time
import urllib.request

import pytest
import yaml

from conftest import PLUGIN, cli, run_hook
from odoo_master.odoo.scaffold import render
from odoo_master.odoo.validate import validate


# ------------------------------------------------------------------ scaffold
@pytest.mark.parametrize("series", ["16.0", "17.0", "18.0", "19.0", "20.0"])
def test_scaffold_is_version_correct_and_valid(tmp_path, series):
    files = render("om_asset", series, model="om.asset", depends=["base", "mail"])
    for rel, content in files.items():
        p = tmp_path / "om_asset" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    res = validate(tmp_path, series=series, with_js=False)
    assert res["passed"], [f for f in res["findings"] if f["severity"] == "error"]
    views = files["views/om_asset_views.xml"]
    model = files["models/om_asset.py"]
    v = int(series.split(".")[0])
    assert ("<list>" in views) == (v >= 18) and ("<tree>" in views) == (v < 18)
    assert ("attrs=" in views) == (v < 17)
    assert ("models.Constraint" in model) == (v >= 19) and ("_sql_constraints" in model) == (v < 19)
    assert ("security/ir.access.csv" in files) == (v >= 20)
    assert ("privilege_id" in files["security/security.xml"]) == (v >= 19)
    assert ('"group_ids"' in files["tests/test_om_asset.py"]) == (v >= 19)


def test_scaffold_refuses_overwrite_and_bad_names(tmp_path):
    rc, out, _ = cli("scaffold", "om_x", "--series", "18.0", "--path", str(tmp_path), root=tmp_path)
    assert rc == 0 and out["validation"]["passed"]
    rc, _, err = cli("scaffold", "om_x", "--series", "18.0", "--path", str(tmp_path), root=tmp_path)
    assert rc != 0
    with pytest.raises(ValueError):
        render("Bad-Name", "18.0")


# ------------------------------------------------------------------ lookup / doctor / init / status / soft
def test_lookup_offline():
    rc, m, _ = cli("lookup", "model", "sale.order", "--series", "17.0")
    assert m["defined_in"] == "sale" and "sale_stock" in m["extended_in"]
    rc, mod, _ = cli("lookup", "module", "sale_management", "--series", "18.0")
    assert "sale" in mod["depends_closure"] and "sales_team" in mod["depends_closure"]
    rc, unk, _ = cli("lookup", "model", "x.nothing", "--series", "18.0")
    assert unk["known"] is False and unk["note"]


def test_doctor_and_soft_mode(tmp_path):
    rc, d, _ = cli("doctor", "--quick", root=tmp_path)
    assert rc == 0 and {c["check"] for c in d["checks"]} >= {"python", "python:yaml", "git", "docker", "state dir"}
    p = subprocess.run([str(PLUGIN / "bin/odoo-master"), "--soft", "--root", str(tmp_path / "missing"), "workflow", "status", "-e", "nope"],
                       capture_output=True, text=True)
    assert p.returncode == 0 and p.stdout.startswith("unavailable:")
    p = subprocess.run([str(PLUGIN / "bin/odoo-master"), "--max-lines", "2", "lookup", "model", "sale.order", "--series", "18.0"],
                       capture_output=True, text=True)
    assert p.stdout.count("\n") == 3 and "more lines" in p.stdout


def test_init_merges_settings_additively(fx):
    root = fx("odoo18_project")
    (root / ".claude").mkdir()
    (root / ".claude/settings.json").write_text(json.dumps({"permissions": {"allow": ["Bash(make *)"]}, "model": "x"}))
    rc, r, _ = cli("init", "--events", "--settings", root=root)
    s = json.loads((root / ".claude/settings.json").read_text())
    assert s["model"] == "x" and "Bash(make *)" in s["permissions"]["allow"] and "Bash(odoo-master *)" in s["permissions"]["allow"]
    assert "Bash(git push --force*)" in s["permissions"]["deny"]
    assert (root / ".claude/settings.json.bak").exists()
    assert (root / ".odoo-master/config.yaml").exists() and (root / ".odoo-master/events/routes.yaml").exists()
    assert 'default_odoo_version: "18.0"' in (root / ".odoo-master/config.yaml").read_text()
    cli("init", "--settings", root=root)                       # idempotent: no duplicates
    s2 = json.loads((root / ".claude/settings.json").read_text())
    assert s2["permissions"]["allow"].count("Bash(odoo-master *)") == 1
    from odoo_master.schemas import validate_file
    assert validate_file("config", root / ".odoo-master/config.yaml")["valid"]


def test_status_and_watch_diff(tmp_path):
    from odoo_master.ops import _snapshot, diff_snapshots
    from odoo_master.workflow import engine
    (tmp_path / ".odoo-master/workflows").mkdir(parents=True)
    before = _snapshot(tmp_path)
    eid = engine.start("database-investigation", {"request": "x"}, tmp_path)["execution"]
    engine.complete(eid, "intake", "DONE", {}, tmp_path)
    lines = diff_snapshots(before, _snapshot(tmp_path))
    assert any("APPROVAL NEEDED" in ln and eid in ln for ln in lines)
    rc, st, _ = cli("status", root=tmp_path)
    assert st["executions"]["waiting_approval"][0]["step"] == "access-approval"
    rc, b, _ = cli("status", "--brief", root=tmp_path)
    assert "APPROVAL:" in b


def test_plugin_options_bridge(tmp_path, monkeypatch):
    from odoo_master.config import load_config
    rc, out = run_hook("session-start", {"cwd": str(tmp_path), "session_id": "o1", "source": "startup"},
                       env={"CLAUDE_PLUGIN_OPTION_AUTONOMY": "autonomous", "CLAUDE_PLUGIN_OPTION_POSTGRES_IMAGE": "postgres:17"})
    assert rc == 0
    cfg = load_config(tmp_path)                               # no env vars here: read from the persisted file
    assert cfg["autonomy"] == "autonomous" and cfg["runtime"]["postgres_image"] == "postgres:17"


# ------------------------------------------------------------------ new hooks
def test_subagent_start_and_stop_contract(fx):
    root = fx("odoo19_project")
    run_hook("session-start", {"cwd": str(root), "session_id": "a1", "source": "startup"})
    rc, out = run_hook("subagent-start", {"cwd": str(root), "session_id": "a1", "agent_type": "odoo-master:odoo-developer", "agent_id": "x"})
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "Odoo series: 19.0" in ctx and "STATUS:" in ctx
    assert run_hook("subagent-start", {"cwd": str(root), "agent_type": "general-purpose"})[1] == ""
    rc, out = run_hook("subagent-stop", {"cwd": str(root), "session_id": "a1", "agent_type": "odoo-master:qa-engineer",
                                         "last_assistant_message": "all good", "stop_hook_active": False})
    assert out["decision"] == "block"
    assert run_hook("subagent-stop", {"cwd": str(root), "session_id": "a1", "agent_type": "odoo-master:qa-engineer",
                                      "last_assistant_message": "all good", "stop_hook_active": True})[1] == ""
    assert run_hook("subagent-stop", {"cwd": str(root), "session_id": "a1", "agent_type": "odoo-master:qa-engineer",
                                      "last_assistant_message": "STATUS: DONE\nverified static"})[1] == ""
    run_hook("session-end", {"cwd": str(root), "session_id": "a1", "reason": "other"})
    rec = json.loads((root / ".odoo-master/logs/sessions.jsonl").read_text().splitlines()[-1])
    assert rec["agent_statuses"] == [None, None, "DONE"]


def test_evidence_capture_hook(fx):
    root = fx("odoo18_project")
    p = subprocess.run([str(PLUGIN / "bin/odoo-master"), "--root", str(root), "validate"], capture_output=True, text=True)
    rc, out = run_hook("evidence-capture", {"cwd": str(root), "session_id": "e1", "tool_name": "Bash",
                                            "tool_input": {"command": "odoo-master validate"}, "tool_response": {"stdout": p.stdout}})
    m = json.loads((root / ".odoo-master/session/e1/last-evidence.json").read_text())
    assert m["kind"] == "validation" and m["status"] == "passed" and m["execution"] == "session-e1"
    rc, out = run_hook("evidence-capture", {"cwd": str(root), "session_id": "e2", "tool_name": "Bash", "tool_input": {"command": "ls"}})
    assert not (root / ".odoo-master/session/e2/last-evidence.json").exists()


# ------------------------------------------------------------------ plugin components
def _fm(p):
    return yaml.safe_load(p.read_text().split("---")[1])


def test_commands_frontmatter_and_no_skill_collision():
    skills = {p.parent.name for p in (PLUGIN / "skills").glob("*/SKILL.md")}
    cmds = list((PLUGIN / "commands").glob("*.md"))
    assert len(cmds) >= 20
    for c in cmds:
        d = _fm(c)
        assert d["description"] and d["disable-model-invocation"] is True
        assert all(t.startswith("Bash(") for t in d["allowed-tools"])
        assert "Bash(${CLAUDE_PLUGIN_ROOT}/bin/odoo-master *)" in d["allowed-tools"]
        assert c.stem not in skills
        body = c.read_text()
        assert ":-" not in body, "shell-style defaults are not a Claude Code substitution"
        for inj in [ln for ln in body.splitlines() if "!`" in ln]:
            cmd = inj.split("!`", 1)[1].split("`", 1)[0]
            assert cmd.startswith("${CLAUDE_PLUGIN_ROOT}/bin/odoo-master --soft") and not any(op in cmd for op in ("|", "&&", "||", ";", ">")), c.name


def test_skill_injections_are_single_commands():
    for s in (PLUGIN / "skills").glob("*/SKILL.md"):
        for ln in s.read_text().splitlines():
            if "!`" in ln:
                cmd = ln.split("!`", 1)[1].split("`", 1)[0]
                assert cmd.startswith("${CLAUDE_PLUGIN_ROOT}/bin/odoo-master --soft") and not any(op in cmd for op in ("|", "&&", "||", ";", ">")), s
                assert "Bash(${CLAUDE_PLUGIN_ROOT}/bin/odoo-master *)" in s.read_text().split("---")[1]


def test_output_style_monitor_lsp_manifest():
    d = _fm(PLUGIN / "output-styles/odoo-engineer.md")
    assert d["name"] == "odoo-engineer" and d["keep-coding-instructions"] is True
    mons = json.loads((PLUGIN / "monitors/monitors.json").read_text())
    assert isinstance(mons, list)
    for m in mons:
        assert set(m) <= {"name", "command", "description", "when"} and {"name", "command", "description"} <= set(m)
        assert m.get("when", "always") == "always" or m["when"].split(":", 1)[1] in {p.parent.name for p in (PLUGIN / "skills").glob("*/SKILL.md")}
    lsp = json.loads((PLUGIN / ".lsp.json").read_text())
    allowed = {"command", "extensionToLanguage", "args", "transport", "env", "initializationOptions", "settings", "workspaceFolder",
               "startupTimeout", "shutdownTimeout", "requestTimeout", "restartOnCrash", "maxRestarts", "diagnostics"}
    for name, cfg in lsp.items():
        assert set(cfg) <= allowed and cfg["command"] and all(k.startswith(".") for k in cfg["extensionToLanguage"])
    man = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text())
    assert man["engines"]["claude-code"].startswith(">=")
    for k, opt in man["userConfig"].items():
        assert opt["type"] in ("string", "number", "boolean", "directory", "file") and opt["title"] and opt["description"]
    from odoo_master.config import OPTION_KEYS
    assert set(man["userConfig"]) == set(OPTION_KEYS)
    hooks = json.loads((PLUGIN / "hooks/hooks.json").read_text())["hooks"]
    assert {"SubagentStart", "SubagentStop", "SessionEnd"} <= set(hooks)


def test_lsp_server_speaks_lsp_if_installed():
    import shutil
    exe = shutil.which("pyright-langserver")
    if not exe:
        pytest.skip("pyright-langserver not installed")
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"processId": None, "rootUri": None, "capabilities": {}}})
    msg = f"Content-Length: {len(body)}\r\n\r\n{body}".encode()
    p = subprocess.Popen([exe, "--stdio"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    p.stdin.write(msg)
    p.stdin.flush()
    head = p.stdout.read(200)
    p.kill()
    assert b"Content-Length" in head


# ------------------------------------------------------------------ events over real HTTP + Linear
def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_event_receiver_over_http(tmp_path):
    port = _free_port()
    env = {"ODOO_MASTER_GITHUB_WEBHOOK_SECRET": "gh", "PATH": "/usr/bin:/bin"}
    import os
    proc = subprocess.Popen([str(PLUGIN / "bin/odoo-master"), "--root", str(tmp_path), "events", "serve", "--port", str(port)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={**os.environ, **env})
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        body = json.dumps({"action": "labeled", "label": {"name": "odoo-master"}, "issue": {"number": 9},
                           "repository": {"full_name": "acme/erp"}}).encode()
        sig = "sha256=" + hmac.new(b"gh", body, hashlib.sha256).hexdigest()
        req = urllib.request.Request(f"http://127.0.0.1:{port}/events/github", data=body, method="POST",
                                     headers={"X-GitHub-Event": "issues", "X-GitHub-Delivery": "http-1", "X-Hub-Signature-256": sig,
                                              "Content-Type": "application/json"})
        res = json.loads(urllib.request.urlopen(req, timeout=5).read())
        assert res["results"][0]["workflow"] == "github-issue-development"
        bad = urllib.request.Request(f"http://127.0.0.1:{port}/events/github", data=body, method="POST",
                                     headers={"X-GitHub-Event": "issues", "X-Hub-Signature-256": "sha256=00"})
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(bad, timeout=5)
        assert e.value.code == 401
        big = urllib.request.Request(f"http://127.0.0.1:{port}/events/github", data=b"x" * (3 * 1024 * 1024), method="POST")
        with pytest.raises((urllib.error.HTTPError, ConnectionError, urllib.error.URLError)):
            urllib.request.urlopen(big, timeout=5)
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_linear_webhook(tmp_path, monkeypatch):
    from odoo_master.integrations.events import handle_event, normalise
    monkeypatch.setenv("ODOO_MASTER_LINEAR_WEBHOOK_SECRET", "ln")
    payload = {"type": "Issue", "action": "create", "webhookId": "w1", "createdAt": "2026-11-26",
               "data": {"identifier": "ENG-12", "title": "Odoo export broken", "labels": [{"name": "odoo-master"}]}}
    evs = normalise("linear", {}, payload)
    assert evs[0]["type"] == "linear.issue.created" and evs[0]["issue"]["key"] == "ENG-12"
    body = json.dumps(payload).encode()
    sig = hmac.new(b"ln", body, hashlib.sha256).hexdigest()
    r = handle_event("linear", {"Linear-Signature": sig}, body, tmp_path)
    assert r["status"] == 200 and r["results"][0]["status"] == "no_route"   # no Linear route enabled by default


def test_version_conflict_guard_and_confirm(fx):
    root = fx("broken_module")
    run_hook("session-start", {"cwd": str(root), "session_id": "c1", "source": "startup"})
    f = str(root / "addons/broken_mod/models/things.py")
    rc, out = run_hook("guard", {"cwd": str(root), "tool_name": "Edit", "tool_input": {"file_path": f, "new_string": "x"}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask" and "--confirm" in out["hookSpecificOutput"]["permissionDecisionReason"]
    rc, res, _ = cli("detect-version", "--confirm", "18.0", root=root)
    assert res["confirmed"] == "18.0" and res["resolved_conflicts"]
    assert run_hook("guard", {"cwd": str(root), "tool_name": "Edit", "tool_input": {"file_path": f, "new_string": "x"}})[1] == ""
    rc, b, _ = cli("detect-version", "--brief", root=root)
    assert "18.0 (confidence confirmed" in b
    rc, _, err = cli("detect-version", "--confirm", "13.5", root=root)
    assert rc == 2
