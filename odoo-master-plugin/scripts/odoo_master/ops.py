"""Operational commands: doctor (environment check), init (project setup), status (dashboard), watch (monitor feed)."""
from __future__ import annotations

import importlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .util import PLUGIN_ROOT, STATE_DIR_NAME, now_iso, read_json, state_dir, write_json

MIN_CLAUDE = (2, 1, 300)


def _ver(cmd: list[str]) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return (r.stdout or r.stderr).strip().splitlines()[0] if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def doctor(root: Path, check_images: bool = True) -> dict:
    checks = []

    def add(name, status, detail, fix=None, needed_for=None):
        checks.append({"check": name, "status": status, "detail": detail, "fix": fix, "needed_for": needed_for})

    py = sys.version_info
    add("python", "ok" if py >= (3, 10) else "fail", sys.version.split()[0], "use Python >= 3.10 (ODOO_MASTER_PYTHON)", "everything")
    for mod, need, fix in (("yaml", "workflows, policies, config", "pip install pyyaml"),
                           ("jsonschema", "full schema validation", "pip install jsonschema"),
                           ("pypdf", "PDF page verification", "pip install pypdf"),
                           ("lxml", "XML line numbers in findings", "pip install lxml")):
        try:
            importlib.import_module(mod)
            add(f"python:{mod}", "ok", "installed", None, need)
        except ImportError:
            add(f"python:{mod}", "fail" if mod == "yaml" else "warn", "missing", fix, need)
    add("git", "ok" if shutil.which("git") else "fail", _ver(["git", "--version"]) or "missing", "install git", "repository analysis")
    if shutil.which("docker"):
        r = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            add("docker", "ok", f"daemon {r.stdout.strip()}", None, "runtime tests, visual QA, source lookup, upgrade_code")
            if check_images:
                imgs = subprocess.run(["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"], capture_output=True, text=True).stdout.split()
                have = sorted(i for i in imgs if i.startswith("odoo:"))
                add("odoo images", "ok" if have else "warn", ", ".join(have) or "none pulled yet",
                    "docker pull odoo:<series> (pulled automatically on first use)", "runtime tests")
        else:
            hint = "start the daemon (dockerd / Docker Desktop)"
            if "pid" in r.stderr.lower() or Path("/var/run/docker.pid").exists():
                hint += "; a stale /var/run/docker.pid after a container restart prevents dockerd from starting — remove it if no dockerd runs"
            add("docker", "warn", "daemon not reachable: " + r.stderr.strip()[:160], hint, "runtime tests")
    else:
        add("docker", "warn", "CLI not installed", "install Docker", "runtime tests (levels reported as missing without it)")
    node = _ver(["node", "--version"])
    add("node", "ok" if node else "warn", node or "missing", "install Node >= 18", "visual QA, best PDF rendering")
    if node:
        pw = subprocess.run(["node", "-e", "require('playwright');console.log('ok')"], capture_output=True, text=True)
        add("playwright", "ok" if pw.returncode == 0 else "warn", "available" if pw.returncode == 0 else "not resolvable",
            "npm i -g playwright && npx playwright install chromium", "visual QA, PDF")
    add("psql", "ok" if shutil.which("psql") else "warn", _ver(["psql", "--version"]) or "missing", "install postgresql-client", "database inspection")
    lsp = shutil.which("pyright-langserver")
    add("pyright-langserver", "ok" if lsp else "info", lsp or "missing (optional)", "npm i -g pyright", "Python diagnostics via the plugin's .lsp.json")
    cv = _ver(["claude", "--version"])
    if cv:
        m = re.search(r"(\d+)\.(\d+)\.(\d+)", cv)
        ok = m and tuple(map(int, m.groups())) >= MIN_CLAUDE
        add("claude-code", "ok" if ok else "warn", cv, "update Claude Code to >= 2.1.300", "plugin features")
    else:
        add("claude-code", "info", "CLI not found on PATH (fine when running inside Claude Code)", None, None)
    try:
        sd = state_dir(root)
        (sd / ".doctor").write_text(now_iso())
        (sd / ".doctor").unlink()
        add("state dir", "ok", str(sd), None, "knowledge files, executions, evidence")
    except OSError as exc:
        add("state dir", "fail", str(exc), "make the project directory writable", "everything")
    worst = "fail" if any(c["status"] == "fail" for c in checks) else "warn" if any(c["status"] == "warn" for c in checks) else "ok"
    return {"root": str(root), "overall": worst, "checks": checks}


CONFIG_TEMPLATE = """# Odoo Master project configuration (schemas/config.schema.json). Every key is optional;
# omitted keys come from the plugin defaults (`odoo-master config` shows the merged result).
autonomy: checkpoint            # checkpoint | autonomous
production_patterns: [prod, production, live]
default_odoo_version: "{version}"
runtime:
  postgres_image: postgres:16
  enterprise_path: ""           # path to Enterprise addons (mounted read-only in runtime tests)
integrations:
  project_repositories: {{}}    # e.g. {{INV: acme/odoo-inventory}}
instructions:
  extra_files: []               # project instruction files agents must read
policies:
  approvals:
    ticket_approval:
      label: odoo-master:approved
"""


def init(root: Path, with_events: bool = False, with_settings: bool = False, force: bool = False) -> dict:
    from .odoo.version import detect
    sd = state_dir(root)
    done = []
    cfg = sd / "config.yaml"
    if cfg.exists() and not force:
        done.append({"file": str(cfg), "action": "kept (exists)"})
    else:
        cfg.write_text(CONFIG_TEMPLATE.format(version=detect(root, max_files=1500).get("version") or ""), encoding="utf-8")
        done.append({"file": str(cfg), "action": "written"})
    if with_events:
        dst = sd / "events" / "routes.yaml"
        if dst.exists() and not force:
            done.append({"file": str(dst), "action": "kept (exists)"})
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(PLUGIN_ROOT / "integrations" / "events" / "routes.yaml", dst)
            done.append({"file": str(dst), "action": "written"})
    if with_settings:
        done.append(merge_settings(root))
    return {"root": str(root), "results": done,
            "next": ["odoo-master analyze --brief", "odoo-master doctor", "/odoo-master:project-intake <request>"]}


def merge_settings(root: Path) -> dict:
    """Merge the recommended permissions into .claude/settings.json. Additive only (never removes a
    rule or changes other keys); a backup is written first."""
    tpl = json.loads((PLUGIN_ROOT / "templates" / "settings" / "project-settings.json").read_text())
    path = root / ".claude" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    cur = read_json(path, default={}) if path.exists() else {}
    if path.exists():
        shutil.copy(path, path.with_suffix(".json.bak"))
    perms = cur.setdefault("permissions", {})
    added = {}
    for key in ("allow", "ask", "deny"):
        have = perms.setdefault(key, [])
        new = [r for r in tpl.get("permissions", {}).get(key, []) if r not in have]
        have.extend(new)
        added[key] = new
    write_json(path, cur)
    return {"file": str(path), "action": "merged", "added_rules": added, "backup": str(path.with_suffix(".json.bak")) if path.with_suffix(".json.bak").exists() else None}


def status(root: Path) -> dict:
    sd = root / STATE_DIR_NAME
    ver = read_json(sd / "odoo-version.json") or {}
    inv = read_json(sd / "project-inventory.json") or {}
    execs, waiting = [], []
    for p in sorted((sd / "executions").glob("*.json")) if (sd / "executions").exists() else []:
        ex = read_json(p) or {}
        if "steps" not in ex:
            continue
        execs.append({"id": ex["id"], "workflow": ex["workflow"], "status": ex["status"], "ticket": ex.get("ticket"), "updated_at": ex.get("updated_at")})
        for sid, st in ex["steps"].items():
            if st["status"] == "WAITING_APPROVAL":
                waiting.append({"execution": ex["id"], "step": sid, "ticket": ex.get("ticket"), "since": st.get("requested_at")})
    reg = read_json(sd / "mcp-registry.json") or {}
    from .odoo import runtime
    events = sorted((sd / "events" / "records").glob("*.json")) if (sd / "events" / "records").exists() else []
    return {
        "root": str(root), "odoo_version": ver.get("version"), "confidence": ver.get("confidence"),
        "modules": (inv.get("summary") or {}).get("module_count") if inv else (read_json(sd / "session" / "bootstrap.json") or {}).get("module_count"),
        "analysis_at": inv.get("generated_at"),
        "analysis_hint": None if inv else "full analysis not run yet: `odoo-master analyze --brief`",
        "executions": {"active": [e for e in execs if e["status"] in ("running", "waiting_approval", "blocked", "stalled")],
                       "recent": execs[-10:], "waiting_approval": waiting},
        "mcp": {s: {"provider": e.get("provider"), "status": e.get("status"), "tools": len(e.get("tools", []))} for s, e in (reg.get("servers") or {}).items()},
        "runtime_instances": runtime.status(root),
        "event_records": [p.stem for p in events[-10:]],
    }


def _snapshot(root: Path) -> dict:
    sd = root / STATE_DIR_NAME
    snap = {}
    for p in sorted((sd / "executions").glob("*.json")) if (sd / "executions").exists() else []:
        ex = read_json(p) or {}
        if "steps" in ex:
            snap[f"exec:{ex['id']}"] = (ex["status"], tuple(sorted(k for k, v in ex["steps"].items() if v["status"] == "WAITING_APPROVAL")), ex.get("ticket"), ex["workflow"])
    for p in sorted((sd / "events" / "records").glob("*.json")) if (sd / "events" / "records").exists() else []:
        rec = read_json(p) or {}
        snap[f"event:{p.stem}"] = (rec.get("status"), rec.get("event"), rec.get("workflow"), (rec.get("inputs") or {}))
    errs = sd / "logs" / "hook-errors.jsonl"
    snap["hook_errors"] = sum(1 for _ in errs.open()) if errs.exists() else 0
    return snap


def diff_snapshots(old: dict, new: dict) -> list[str]:
    lines = []
    for k, v in new.items():
        if k == "hook_errors":
            if v > old.get(k, 0):
                lines.append(f"[odoo-master] {v - old.get(k, 0)} new hook error(s) — see .odoo-master/logs/hook-errors.jsonl")
            continue
        if old.get(k) == v:
            continue
        kind, ident = k.split(":", 1)
        if kind == "exec":
            st, waiting, ticket, wf = v
            if waiting and (not old.get(k) or old[k][1] != waiting):
                lines.append(f"[odoo-master] APPROVAL NEEDED: execution {ident} ({wf}, ticket {ticket}) waits at {', '.join(waiting)} — present the plan and run `odoo-master workflow approve`")
            elif st in ("completed", "failed", "rejected", "blocked", "stalled") and (not old.get(k) or old[k][0] != st):
                lines.append(f"[odoo-master] execution {ident} ({wf}, ticket {ticket}) is now {st}")
        elif kind == "event" and k not in old:
            st, ev, wf, inputs = v
            lines.append(f"[odoo-master] new event {ev} → workflow {wf} {json.dumps(inputs)} ({st})")
    return lines


def watch(root: Path, interval: float = 15.0, once: bool = False, iterations: int | None = None) -> None:
    """Print one line per noteworthy change (approvals needed, executions finished, new webhook events,
    hook errors). Designed for a Claude Code monitor: each stdout line becomes a notification."""
    prev = _snapshot(root)
    if once:
        return
    n = 0
    while iterations is None or n < iterations:
        time.sleep(interval)
        cur = _snapshot(root)
        for line in diff_snapshots(prev, cur):
            print(line, flush=True)
        prev = cur
        n += 1
