"""Evidence collection: items with sha256, verification levels achieved vs. missing, verification."""
from __future__ import annotations

from pathlib import Path

from ..config import load_config, policy
from ..util import now_iso, read_json, sha256_file, state_dir, write_json

LEVELS = ["static", "unit", "integration", "runtime", "database", "browser", "production"]
KINDS = ["validation", "unit-test", "integration-test", "runtime-test", "database-check", "browser-check", "screenshot", "review",
         "migration-check", "log-summary", "report", "command", "other"]
STATUSES = ["passed", "failed", "skipped", "passed_no_tests", "info"]


def _file(execution: str, root) -> Path:
    return state_dir(root) / "evidence" / execution / "evidence.json"


def add(execution: str, kind: str, level: str, path: str | None, root=None, summary: str | None = None, status: str | None = None,
        command: str | None = None) -> dict:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    if level not in LEVELS:
        raise ValueError(f"level must be one of {LEVELS}")
    status = status or "info"
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    f = _file(execution, root)
    data = read_json(f) or {"execution": execution, "items": []}
    item = {"kind": kind, "level": level, "status": status, "path": None, "sha256": None, "summary": summary, "command": command,
            "recorded_at": now_iso()}
    if path:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(path)
        item["path"] = str(p.resolve())
        item["sha256"] = sha256_file(p) if p.is_file() else None
    data["items"].append(item)
    write_json(f, data)
    ex = read_json(state_dir(root) / "executions" / f"{execution}.json")
    if ex is not None:
        ex.setdefault("evidence", []).append({"kind": kind, "level": level, "status": status, "path": item["path"]})
        write_json(state_dir(root) / "executions" / f"{execution}.json", ex)
    return item


def _intent_of(execution: str, root) -> str | None:
    ex = read_json(state_dir(root) / "executions" / f"{execution}.json") or {}
    wf = ex.get("workflow")
    if not wf:
        return None
    cfg = load_config(root)
    for intent, name in ((cfg.get("workflows") or {}).get("default_for_intent") or {}).items():
        if name == wf:
            return intent
    return None


def manifest(execution: str, root=None) -> dict:
    data = read_json(_file(execution, root)) or {"execution": execution, "items": []}
    achieved = sorted({i["level"] for i in data["items"] if i["status"] == "passed"}, key=LEVELS.index)
    failed = sorted({i["level"] for i in data["items"] if i["status"] == "failed"}, key=LEVELS.index)
    intent = _intent_of(execution, root)
    required = (policy(load_config(root), "testing").get("required_levels") or {}).get(intent or "", [])
    ex = read_json(state_dir(root) / "executions" / f"{execution}.json") or {}
    out = {"execution": execution, "ticket": ex.get("ticket"), "generated_at": now_iso(), "intent": intent, "items": data["items"],
           "levels_required": required, "levels_achieved": achieved, "levels_failed": failed,
           "levels_missing": [lvl for lvl in required if lvl not in achieved],
           "complete": bool(required) and all(lvl in achieved for lvl in required) and not failed}
    write_json(state_dir(root) / "evidence" / execution / "manifest.json", out)
    return out


def verify(execution: str, root=None) -> dict:
    data = read_json(_file(execution, root)) or {"items": []}
    problems = []
    for it in data["items"]:
        if it.get("path") and it.get("sha256"):
            p = Path(it["path"])
            if not p.exists():
                problems.append({"path": it["path"], "problem": "missing"})
            elif sha256_file(p) != it["sha256"]:
                problems.append({"path": it["path"], "problem": "hash mismatch (modified after recording)"})
    return {"execution": execution, "items": len(data["items"]), "ok": not problems, "problems": problems}
