"""MCP capability registry.

Sources of truth, in order:
  1. tools registered from the live Claude Code session (`odoo-master mcp register`), which can see
     OAuth-authenticated servers;
  2. direct probes of stdio / unauthenticated HTTP servers (`odoo-master mcp probe`);
  3. configuration only (`odoo-master mcp servers`) — status "configured", tools unknown.

Each tool is classified into provider + capabilities + access (read/write/destructive) using
integrations/<provider>/capabilities.yaml, project overrides in .odoo-master/integrations/*.yaml,
MCP tool annotations (readOnlyHint/destructiveHint) and verb heuristics.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..util import PLUGIN_ROOT, load_yaml, now_iso, read_json, redact, state_dir, write_json
from . import client


def _norm(name: str) -> str:
    s = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name)
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _profiles(root: Path | None = None) -> list[dict]:
    profs = []
    base = PLUGIN_ROOT / "integrations"
    for p in sorted(base.glob("*/capabilities.yaml")):
        d = load_yaml(p)
        if "profiles" in d:
            profs += d["profiles"]
        elif d.get("provider"):
            profs.append(d)
    proj = state_dir(root, create=False) / "integrations"
    if proj.is_dir():
        for p in sorted(proj.glob("*.yaml")):
            d = load_yaml(p)
            profs = [d] + profs if d.get("provider") else profs
    return profs


def _taxonomy() -> dict:
    return load_yaml(PLUGIN_ROOT / "integrations" / "mcp" / "capability-taxonomy.yaml")


def provider_for(server: str, tools: list[dict], profiles: list[dict]) -> str | None:
    for prof in profiles:
        if any(re.search(pat, server or "", re.I) for pat in prof.get("server_patterns", [])):
            return prof["provider"]
    names = " ".join(_norm(t.get("name", "")) for t in tools)
    for prof in profiles:
        hits = sum(1 for rule in prof.get("tools", []) if re.search(rule["match"], names))
        if prof["provider"] not in ("odoo-master",) and hits >= 3:
            return prof["provider"]
    return None


def classify_tool(tool: dict, provider: str | None, profiles: list[dict], tax: dict) -> dict:
    n = _norm(tool.get("name", ""))
    caps, access_override = [], None
    prof = next((p for p in profiles if p["provider"] == provider), None)
    if prof:
        for rule in prof.get("tools", []):
            if re.search(rule["match"], n):
                caps += [c for c in rule["capabilities"] if c not in caps]
                access_override = rule.get("access", access_override)
                if caps:
                    break
    ann = tool.get("annotations") or {}
    access = "unknown"
    if ann.get("readOnlyHint") is True:
        access = "read"
    elif ann.get("destructiveHint") is True:
        access = "destructive"
    else:
        words = set(n.split("_"))
        verbs = tax.get("generic_verbs", {})
        if words & set(verbs.get("destructive", [])):
            access = "destructive"
        elif words & set(verbs.get("write", [])):
            access = "write"
        elif words & set(verbs.get("read", [])):
            access = "read"
        elif caps:
            levels = [tax["capabilities"].get(c, {}).get("access", "write") for c in caps]
            access = "destructive" if "destructive" in levels else "write" if "write" in levels else "read"
    if access_override:
        access = access_override
    req = ((tool.get("inputSchema") or {}).get("required") or [])
    return {"name": tool.get("name"), "description": (tool.get("description") or "")[:300], "capabilities": caps,
            "access": access, "input_required": req, "annotations": ann or None}


def configured_servers(root: Path | None = None) -> dict:
    """Read MCP server *configuration* (names, transport, commands) — env values and headers redacted."""
    root = Path(root) if root else None
    from ..util import find_project_root
    root = root or find_project_root()
    found = {}

    def add(name, cfg, source):
        c = {"type": cfg.get("type") or ("stdio" if "command" in cfg else None), "source": source}
        if "command" in cfg:
            c["command"] = cfg["command"]
            c["args"] = cfg.get("args", [])
        if "url" in cfg:
            c["url"] = cfg["url"]
        if cfg.get("env"):
            c["env_keys"] = sorted(cfg["env"].keys())
        if cfg.get("headers"):
            c["header_keys"] = sorted(cfg["headers"].keys())
        found.setdefault(name, redact(c))

    for p, src in ((root / ".mcp.json", "project"), (PLUGIN_ROOT / ".mcp.json", "plugin:odoo-master")):
        d = read_json(p) or {}
        for n, cfg in (d.get("mcpServers") or {}).items():
            add(n, cfg, src)
    home = Path.home() / ".claude.json"
    d = read_json(home) or {}
    for n, cfg in ((d.get("projects") or {}).get(str(root), {}).get("mcpServers") or {}).items():
        add(n, cfg, "local")
    for n, cfg in (d.get("mcpServers") or {}).items():
        add(n, cfg, "user")
    return {"root": str(root), "servers": found,
            "note": "claude.ai connectors and servers added in other ways only appear via session discovery (`mcp register`)."}


def _raw_configs(root: Path) -> dict:
    out = {}
    for p in (root / ".mcp.json", PLUGIN_ROOT / ".mcp.json"):
        for n, cfg in ((read_json(p) or {}).get("mcpServers") or {}).items():
            cfg = dict(cfg)
            cfg_s = json.dumps(cfg).replace("${CLAUDE_PLUGIN_ROOT}", str(PLUGIN_ROOT)).replace("${CLAUDE_PROJECT_DIR}", str(root))
            out.setdefault(n, json.loads(cfg_s))
    d = read_json(Path.home() / ".claude.json") or {}
    for n, cfg in ((d.get("projects") or {}).get(str(root), {}).get("mcpServers") or {}).items():
        out.setdefault(n, cfg)
    for n, cfg in (d.get("mcpServers") or {}).items():
        out.setdefault(n, cfg)
    return out


def load_registry(root: Path | None = None) -> dict:
    return read_json(state_dir(root) / "mcp-registry.json") or {"updated_at": None, "servers": {}}


def _save(reg: dict, root) -> dict:
    reg["updated_at"] = now_iso()
    write_json(state_dir(root) / "mcp-registry.json", reg)
    return reg


def _store_server(reg, name, tools, status, source, profiles, tax, extra=None):
    provider = provider_for(name, tools, profiles)
    entry = {"provider": provider, "status": status, "source": source, "updated_at": now_iso(),
             "tools": [dict(classify_tool(t, provider, profiles, tax), qualified_name=f"mcp__{name}__{t.get('name')}") for t in tools]}
    if extra:
        entry.update(extra)
    reg["servers"][name] = entry
    return entry


def probe_all(root: Path | None = None, timeout: int = 20, names: list[str] | None = None) -> dict:
    from ..util import find_project_root
    root = Path(root) if root else find_project_root()
    reg = load_registry(root)
    profiles, tax = _profiles(root), _taxonomy()
    results = {}
    for name, cfg in _raw_configs(root).items():
        if names and name not in names:
            continue
        res = client.probe(cfg, timeout=timeout)
        status = res.get("status", "unknown")
        if status == "connected":
            _store_server(reg, name, res.get("tools", []), "connected", "probe", profiles, tax, {"server_info": res.get("server")})
        else:
            prev = reg["servers"].get(name, {})
            reg["servers"][name] = {**prev, "status": status, "source": prev.get("source", "probe"), "last_error": str(res.get("error"))[:300],
                                    "tools": prev.get("tools", [])}
        results[name] = {"status": status, "tools": len(res.get("tools", [])), "error": res.get("error")}
    _save(reg, root)
    return {"probed": results, "registry": str(state_dir(root) / "mcp-registry.json")}


def register_tools(tools: list[dict] | dict, root: Path | None = None, server: str | None = None) -> dict:
    """Register tools observed in the live session. Accepts a list of tool objects
    ({name, description, inputSchema, annotations, server?}) or {"server": [...tools]}.
    Qualified names `mcp__<server>__<tool>` are split automatically."""
    reg = load_registry(root)
    profiles, tax = _profiles(root), _taxonomy()
    by_server: dict[str, list] = {}
    if isinstance(tools, dict):
        by_server = {k: list(v) for k, v in tools.items()}
    else:
        for t in tools:
            t = dict(t)
            name = t.get("name", "")
            srv = t.pop("server", None) or server
            if name.startswith("mcp__") and name.count("__") >= 2:
                _, srv2, tool = name.split("__", 2)
                srv = srv or srv2
                t["name"] = tool
            by_server.setdefault(srv or "unknown", []).append(t)
    summary = {}
    for srv, tl in by_server.items():
        e = _store_server(reg, srv, tl, "connected", "session", profiles, tax)
        summary[srv] = {"provider": e["provider"], "tools": len(tl),
                        "capabilities": sorted({c for t in e["tools"] for c in t["capabilities"]})}
    _save(reg, root)
    return {"registered": summary}


def resolve(capability: str, root: Path | None = None, provider: str | None = None) -> dict:
    reg = load_registry(root)
    out = []
    for srv, e in (reg.get("servers") or {}).items():
        if provider and e.get("provider") != provider:
            continue
        for t in e.get("tools", []):
            if capability in t.get("capabilities", []):
                out.append({"server": srv, "provider": e.get("provider"), "status": e.get("status"), "tool": t["name"],
                            "qualified_name": t.get("qualified_name"), "access": t["access"], "input_required": t.get("input_required")})
    out.sort(key=lambda x: (x["status"] != "connected", x["server"]))
    tax = _taxonomy()["capabilities"].get(capability)
    res = {"capability": capability, "known_capability": bool(tax), "tools": out}
    if not out:
        res["hint"] = ("No registered tool provides this capability. Discover tools (mcp-integration skill), "
                       "or connect a server for it, or continue without it and say so.")
    return res


def recent_calls(root: Path | None = None, limit: int = 50) -> list:
    p = state_dir(root) / "logs" / "mcp-calls.jsonl"
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").splitlines()[-limit:]
    return [json.loads(ln) for ln in lines if ln.strip()]
