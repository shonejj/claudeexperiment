"""Claude Code hook adapters (the only Claude-Code-specific code besides runtime/claude_code.py).

Every hook reads the JSON payload from stdin and must never crash the session: internal errors are
reported as a short systemMessage and the hook exits 0 (fail-open). The guard is a guard-rail, not a
security boundary — see docs/security.md.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

from ..util import append_jsonl, find_project_root, now_iso, read_json, state_dir, write_json


def read_payload() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return {}


def project_root(payload: dict) -> Path:
    return find_project_root(payload.get("cwd"))


def session_dir(payload: dict) -> Path:
    sid = (payload.get("session_id") or "unknown").replace("/", "_")[:80]
    d = state_dir(project_root(payload)) / "session" / sid
    d.mkdir(parents=True, exist_ok=True)
    return d


def out(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj))


def safe_main(fn) -> int:
    payload = read_payload()
    try:
        return fn(payload) or 0
    except Exception as exc:  # noqa: BLE001 - fail open, but leave a trace
        try:
            append_jsonl(state_dir(project_root(payload)) / "logs" / "hook-errors.jsonl",
                         {"at": now_iso(), "hook": fn.__module__, "error": repr(exc), "trace": traceback.format_exc()[-2000:]})
        except Exception:
            pass
        out({"systemMessage": f"odoo-master hook {fn.__module__.rsplit('.', 1)[-1]} error (ignored): {exc}"})
        return 0


def changed_files(payload: dict) -> list[str]:
    return (read_json(session_dir(payload) / "changed.json") or {}).get("files", [])


def record_changed(payload: dict, path: str) -> None:
    f = session_dir(payload) / "changed.json"
    data = read_json(f) or {"files": []}
    if path not in data["files"]:
        data["files"].append(path)
    write_json(f, data)
