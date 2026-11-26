import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from odoo_master.mcp import client, registry
from conftest import PLUGIN

TOOLS = [
    {"name": "mcp__atlassian__searchJiraIssuesUsingJql", "description": "Search", "annotations": {"readOnlyHint": True}},
    {"name": "mcp__atlassian__getJiraIssue"},
    {"name": "mcp__atlassian__addCommentToJiraIssue", "inputSchema": {"type": "object", "required": ["issueIdOrKey", "commentBody"]}},
    {"name": "mcp__atlassian__transitionJiraIssue"},
    {"name": "mcp__github__create_pull_request"},
    {"name": "mcp__github__merge_pull_request"},
    {"name": "mcp__github__issue_read"},
    {"name": "mcp__slack__slack_get_thread_replies"},
    {"name": "mcp__slack__slack_reply_to_thread"},
    {"name": "mcp__internal__frobnicate_widget", "annotations": {"destructiveHint": True}},
]


def test_register_classify_resolve(tmp_path):
    res = registry.register_tools(TOOLS, tmp_path)
    assert res["registered"]["atlassian"]["provider"] == "jira"
    assert res["registered"]["github"]["provider"] == "github"
    assert res["registered"]["slack"]["provider"] == "slack"
    assert res["registered"]["internal"]["provider"] is None
    r = registry.resolve("ticket.add_comment", tmp_path)
    assert r["tools"][0]["tool"] == "addCommentToJiraIssue" and r["tools"][0]["access"] == "write"
    assert r["tools"][0]["input_required"] == ["issueIdOrKey", "commentBody"]
    assert registry.resolve("ticket.search", tmp_path)["tools"][0]["access"] == "read"
    merge = registry.resolve("repo.merge", tmp_path)["tools"][0]
    assert merge["access"] == "destructive"
    assert registry.resolve("chat.reply_thread", tmp_path)["tools"][0]["server"] == "slack"
    reg = registry.load_registry(tmp_path)
    internal = reg["servers"]["internal"]["tools"][0]
    assert internal["access"] == "destructive" and internal["capabilities"] == []
    missing = registry.resolve("docs.write", tmp_path)
    assert missing["tools"] == [] and "hint" in missing
    from odoo_master.schemas import validate_data
    assert validate_data("mcp-registry", reg)["valid"]


def test_probe_bundled_stdio_server():
    cfg = {"type": "stdio", "command": "python3", "args": ["-m", "odoo_master.mcp.server"],
           "env": {"PYTHONPATH": str(PLUGIN / "scripts")}}
    res = client.probe(cfg, timeout=20)
    assert res["status"] == "connected"
    names = {t["name"] for t in res["tools"]}
    assert {"detect_version", "validate_modules", "migration_scan", "standard_model_lookup"} <= names
    assert all(t["annotations"]["readOnlyHint"] for t in res["tools"])


def test_bundled_server_tool_call(fx):
    from odoo_master.mcp.server import handle
    root = fx("odoo19_project")
    r = handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "detect_version", "arguments": {"root": str(root)}}})
    assert json.loads(r["result"]["content"][0]["text"])["version"] == "19.0"
    r = handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "standard_model_lookup", "arguments": {"model": "stock.picking", "series": "18.0"}}})
    assert json.loads(r["result"]["content"][0]["text"])["defined_in"] == "stock"
    assert handle({"jsonrpc": "2.0", "id": 5, "method": "nope"})["error"]["code"] == -32601


def test_probe_failures_are_graceful():
    assert client.probe({"type": "stdio", "command": "/nonexistent/server"})["status"] == "failed"
    assert client.probe({"type": "sse", "url": "http://x"})["status"] == "unknown"

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(401)
            self.end_headers()
        def log_message(self, *a):
            pass
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    res = client.probe({"type": "http", "url": f"http://127.0.0.1:{srv.server_port}/mcp"}, timeout=5)
    srv.shutdown()
    assert res["status"] == "needs_auth"


def test_probe_all_and_configured_servers(tmp_path):
    (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {
        "broken": {"command": "/nonexistent/bin", "env": {"API_TOKEN": "supersecretvalue"}},
        "jira": {"type": "http", "url": "http://127.0.0.1:9/mcp", "headers": {"Authorization": "Bearer xyz"}}}}))
    conf = registry.configured_servers(tmp_path)
    assert conf["servers"]["broken"]["env_keys"] == ["API_TOKEN"]
    assert "supersecretvalue" not in json.dumps(conf) and "xyz" not in json.dumps(conf)
    res = registry.probe_all(tmp_path, timeout=3, names=["broken", "jira", "odoo-master"])
    assert res["probed"]["broken"]["status"] == "failed"
    assert res["probed"]["jira"]["status"] == "failed"
    assert res["probed"]["odoo-master"]["status"] == "connected"


def test_env_expansion(monkeypatch):
    monkeypatch.setenv("FOO", "bar")
    assert client.expand("${FOO}-${MISSING:-dflt}-${MISSING2}") == "bar-dflt-${MISSING2}"
