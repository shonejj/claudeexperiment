from conftest import run_hook


def test_guard_bash(fx):
    root = fx("odoo18_project")
    def g(cmd, mode="default"):
        return run_hook("guard", {"cwd": str(root), "tool_name": "Bash", "permission_mode": mode, "tool_input": {"command": cmd}})[1]
    assert g("git push --force origin main")["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert g("git push origin feature") == ""
    assert g("git reset --hard HEAD~1")["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert g("psql -d om_test_1 -c 'TRUNCATE res_partner'")["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert g("psql -d om_test_1 -c 'TRUNCATE res_partner'", "bypassPermissions")["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert g("odoo-bin -d production -u my_module --stop-after-init")["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert g("odoo-bin -d om_test_1 -u my_module --stop-after-init") == ""
    assert g("cat .env")["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert g("docker volume rm odoo-data")["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert g("ls -la") == ""


def test_guard_edit_core_and_secrets(fx):
    root = fx("odoo18_project")
    def e(path, content="x = 1"):
        return run_hook("guard", {"cwd": str(root), "tool_name": "Write", "tool_input": {"file_path": str(root / path), "content": content}})[1]
    assert e("odoo/addons/stock/models/stock_picking.py")["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert e("addons/stock_quality_check/models/x.py") == ""
    assert e("addons/stock_quality_check/models/x.py", "API_KEY = 'abcdef123456'")["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert e(".git/config")["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_post_edit_reports_version_findings(fx):
    root = fx("broken_module")
    xml = root / "addons/broken_mod/views/ok.xml"
    xml.write_text('<odoo><record id="v" model="ir.ui.view"><field name="model">sale.order</field>'
                   '<field name="inherit_id" ref="sale.view_order_form"/><field name="arch" type="xml">'
                   '<field name="name" position="after"><field name="note" attrs="{\'invisible\': True}"/></field></field></record></odoo>')
    (root / ".odoo-master").mkdir()
    (root / ".odoo-master/odoo-version.json").write_text('{"version": "18.0"}')
    rc, out = run_hook("post-edit", {"cwd": str(root), "session_id": "s1", "tool_name": "Edit", "tool_input": {"file_path": str(xml)}})
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "attrs-states-removed" in ctx


def test_stop_gate_blocks_then_gives_up(fx):
    root = fx("broken_module")
    f = root / "addons/broken_mod/models/things.py"
    (root / ".odoo-master").mkdir()
    (root / ".odoo-master/odoo-version.json").write_text('{"version": "18.0"}')
    run_hook("post-edit", {"cwd": str(root), "session_id": "s2", "tool_name": "Edit", "tool_input": {"file_path": str(f)}})
    decisions = [run_hook("stop-gate", {"cwd": str(root), "session_id": "s2"})[1] for _ in range(4)]
    assert [d.get("decision") for d in decisions[:3]] == ["block"] * 3
    assert "py-sql-injection" in decisions[0]["reason"]
    assert "remain after" in decisions[3]["systemMessage"]


def test_stop_gate_silent_without_changes(fx):
    root = fx("odoo18_project")
    assert run_hook("stop-gate", {"cwd": str(root), "session_id": "s3"})[1] == ""


def test_session_start_context(fx):
    root = fx("odoo19_project")
    rc, out = run_hook("session-start", {"cwd": str(root), "session_id": "s4", "source": "startup"})
    assert rc == 0 and "Odoo version: 19.0" in out and "/odoo-master:project-intake" in out
    rc, out = run_hook("session-start", {"cwd": str(root / "addons"), "session_id": "s4", "source": "compact"})
    assert "19.0" in out


def test_session_start_non_odoo(tmp_path):
    (tmp_path / "app.py").write_text("print('hi')\n")
    rc, out = run_hook("session-start", {"cwd": str(tmp_path), "session_id": "s5", "source": "startup"})
    assert "general software engineering mode" in out


def test_prompt_refs_and_mcp_failure(fx):
    root = fx("odoo18_project")
    rc, out = run_hook("prompt", {"cwd": str(root), "prompt": "plan INV-42 please https://acme.slack.com/archives/C123/p1764100000000100"})
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "INV-42" in ctx and "Slack thread" in ctx
    assert run_hook("prompt", {"cwd": str(root), "prompt": "hello there"})[1] == ""
    rc, out = run_hook("mcp-failure", {"cwd": str(root), "session_id": "s", "tool_name": "mcp__atlassian__getJiraIssue",
                                        "error": "401 Unauthorized token=abcdef1234567890"})
    assert "reconnect" in out["hookSpecificOutput"]["additionalContext"]
    log = (root / ".odoo-master/logs/mcp-calls.jsonl").read_text()
    assert "abcdef1234567890" not in log and "atlassian" in log


def test_precompact_and_bad_payload(fx):
    root = fx("odoo18_project")
    rc, out = run_hook("pre-compact", {"cwd": str(root), "session_id": "s6", "trigger": "auto"})
    assert "Preserve verbatim" in out
    import subprocess, sys
    from conftest import PLUGIN
    p = subprocess.run([sys.executable, str(PLUGIN / "scripts/hook.py"), "guard"], input="not json", capture_output=True, text=True, cwd=root)
    assert p.returncode == 0
