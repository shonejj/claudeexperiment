"""Bundled stdio MCP server `odoo-master` (read-only project intelligence).

Purpose: expose the harness-independent core to any MCP-capable agent runtime (Claude Code, Codex,
other harnesses) — the portability seam described in docs/architecture.md. All tools are read-only
and annotated so. Protocol: JSON-RPC 2.0 over newline-delimited stdio, MCP 2025-06-18.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROTOCOL = "2025-06-18"

TOOLS = [
    {"name": "detect_version", "title": "Detect Odoo version",
     "description": "Detect the Odoo series of a project with confidence, signals (file:line) and conflicts.",
     "inputSchema": {"type": "object", "properties": {"root": {"type": "string", "description": "project root"}}, "required": ["root"]}},
    {"name": "project_summary", "title": "Odoo project summary",
     "description": "Inventory summary: custom modules, versions, dependencies, model/view/test counts and findings.",
     "inputSchema": {"type": "object", "properties": {"root": {"type": "string"}}, "required": ["root"]}},
    {"name": "validate_modules", "title": "Validate Odoo modules",
     "description": "Static validation (manifest, XML, security, Python, version rules). Returns findings with file:line.",
     "inputSchema": {"type": "object", "properties": {"root": {"type": "string"}, "series": {"type": "string"},
                                                       "modules": {"type": "array", "items": {"type": "string"}}}, "required": ["root"]}},
    {"name": "migration_scan", "title": "Scan migration blockers",
     "description": "List code changes needed to move custom modules from one Odoo series to another.",
     "inputSchema": {"type": "object", "properties": {"root": {"type": "string"}, "source": {"type": "string"}, "target": {"type": "string"}},
                     "required": ["root", "source", "target"]}},
    {"name": "standard_model_lookup", "title": "Where is a standard model defined",
     "description": "For an Odoo series, return the Community module defining a model and the modules extending it.",
     "inputSchema": {"type": "object", "properties": {"model": {"type": "string"}, "series": {"type": "string"}}, "required": ["model", "series"]}},
    {"name": "workflow_status", "title": "Workflow execution status",
     "description": "Status of an odoo-master workflow execution (or list executions when id is omitted).",
     "inputSchema": {"type": "object", "properties": {"root": {"type": "string"}, "execution": {"type": "string"}}, "required": ["root"]}},
]
for t in TOOLS:
    t["annotations"] = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}


def call(name: str, a: dict):
    root = Path(a.get("root", ".")).resolve()
    if name == "detect_version":
        from ..odoo.version import detect
        return detect(root)
    if name == "project_summary":
        from ..odoo.inventory import scan, summary
        from ..odoo.version import detect
        v = detect(root).get("version")
        return {"odoo_version": v, **summary(scan(root, series=v))}
    if name == "validate_modules":
        from ..odoo.validate import validate
        res = validate(root, series=a.get("series"), modules=a.get("modules"))
        res["findings"] = res["findings"][:200]
        return res
    if name == "migration_scan":
        from ..odoo.migration import scan
        return scan(root, a["source"], a["target"])
    if name == "standard_model_lookup":
        from ..odoo import standard_models
        m = standard_models(a["series"])
        return {"model": a["model"], "series": a["series"], "defined_in": m["defined_in"].get(a["model"]),
                "extended_in": m["extended_in"].get(a["model"], [])}
    if name == "workflow_status":
        from ..workflow import engine
        return engine.status(a["execution"], root) if a.get("execution") else engine.list_executions(root)
    raise KeyError(name)


def handle(msg: dict):
    mid, method = msg.get("id"), msg.get("method")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": PROTOCOL, "capabilities": {"tools": {"listChanged": False}},
                                                       "serverInfo": {"name": "odoo-master", "version": "0.1.0"},
                                                       "instructions": "Read-only Odoo project intelligence from the odoo-master plugin."}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        p = msg.get("params") or {}
        try:
            data = call(p.get("name"), p.get("arguments") or {})
            text = json.dumps(data, default=str)[:200_000]
            return {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": text}], "isError": False}}
        except KeyError as exc:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"unknown tool or argument {exc}"}}
        except Exception as exc:  # noqa: BLE001 - tool errors are reported in-band per MCP
            return {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": f"error: {exc}"}], "isError": True}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if mid is None:
        return None  # notification
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
