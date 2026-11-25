"""SessionStart bootstrap (startup | resume | clear | compact).

Idempotent; writes only tool-owned files under .odoo-master/; never connects to databases; never
overwrites project instructions. Prints a compact context block (stdout is added to the session context).
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from ..config import load_config
from ..util import read_json, state_dir, write_json, now_iso
from . import project_root, safe_main

MAX_CONTEXT_CHARS = 2600


def bootstrap(root: Path, source: str = "startup") -> dict:
    cfg = load_config(root)
    sd = state_dir(root)
    inv_path = sd / "project-inventory.json"
    ver_path = sd / "odoo-version.json"
    from ..odoo.version import detect
    ver = read_json(ver_path)
    if not ver or source in ("startup", "clear"):
        ver = detect(root, max_files=1500)
        write_json(ver_path, ver)
    inv = read_json(inv_path) or {}
    stale = (not inv) or (time.time() - inv_path.stat().st_mtime > 86400 if inv_path.exists() else True)
    from ..odoo.inventory import find_modules, classify_module_location
    custom = [m for m in find_modules(root) if classify_module_location(m, root) == "custom"] if stale else None
    executions = []
    ex_dir = sd / "executions"
    if ex_dir.exists():
        for p in sorted(ex_dir.glob("*.json"))[-30:]:
            ex = read_json(p) or {}
            if ex.get("status") in ("running", "waiting_approval", "blocked", "stalled"):
                executions.append({"id": ex["id"], "workflow": ex["workflow"], "status": ex["status"], "ticket": ex.get("ticket"),
                                   "waiting": [k for k, v in ex["steps"].items() if v["status"] in ("RUNNING", "WAITING_APPROVAL")]})
    reg = read_json(sd / "mcp-registry.json") or {}
    caps = sorted({c for s in (reg.get("servers") or {}).values() for t in s.get("tools", []) for c in t.get("capabilities", [])})
    info = {
        "generated_at": now_iso(), "source": source, "root": str(root),
        "odoo_version": ver.get("version"), "confidence": ver.get("confidence"), "conflicts": len(ver.get("conflicts") or []),
        "is_odoo_project": bool(ver.get("version") or (inv.get("summary") or {}).get("module_count") or (custom and len(custom))),
        "module_count": (inv.get("summary") or {}).get("module_count") if inv else len(custom or []),
        "inventory_stale": stale, "autonomy": cfg.get("autonomy"),
        "active_executions": executions, "mcp_capabilities": caps,
        "docker": bool(os.environ.get("DOCKER_HOST")) or Path("/var/run/docker.sock").exists(),
    }
    write_json(sd / "session" / "bootstrap.json", info)
    return info


def render(info: dict) -> str:
    lines = ["[odoo-master] Odoo engineering plugin active."]
    if info["is_odoo_project"]:
        lines.append(f"- Odoo version: {info['odoo_version'] or 'unknown'} (confidence {info['confidence']})"
                     + (f" — {info['conflicts']} CONFLICTING signal(s): confirm the version before editing." if info["conflicts"] else ""))
        lines.append(f"- Custom modules: {info['module_count']}" + (" (project analysis stale/missing: run `odoo-master analyze --brief` or /odoo-master:project-intake before planning)" if info["inventory_stale"] else ""))
        lines.append("- Knowledge files: .odoo-master/project-context.md, project-inventory.json, architecture-map.json, module-dependency-map.json")
    else:
        lines.append("- No Odoo modules detected: general software engineering mode (skills still apply; Odoo-specific checks are inactive).")
    lines.append(f"- Autonomy: {info['autonomy']} (approval gates {'wait for a human' if info['autonomy'] == 'checkpoint' else 'auto-approve low risk only'}).")
    if info["active_executions"]:
        lines.append("- RESUME active workflow executions (call `odoo-master workflow next -e <id>`):")
        for e in info["active_executions"][:5]:
            lines.append(f"  - {e['id']} {e['workflow']} [{e['status']}] ticket={e['ticket']} steps={','.join(e['waiting'])}")
    if info["mcp_capabilities"]:
        lines.append(f"- Registered MCP capabilities: {', '.join(info['mcp_capabilities'][:20])}")
    lines.append("- Entry points: /odoo-master:project-intake (any request), /odoo-master:jira-management, /odoo-master:odoo-migration, "
                 "/odoo-master:mcp-integration. Rules: never edit Odoo core; follow the reuse ladder; cite file:line; never claim untested levels.")
    text = "\n".join(lines)
    return text[:MAX_CONTEXT_CHARS]


def main(payload: dict) -> int:
    root = project_root(payload)
    info = bootstrap(root, payload.get("source", "startup"))
    print(render(info))
    return 0


def run() -> int:
    return safe_main(main)
