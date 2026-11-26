"""Subagent and session lifecycle hooks.

SubagentStart (matcher odoo-master:.*): injects the project facts every specialist needs (Odoo series,
active executions/tickets, instruction pointers) so briefs stay short and nothing is guessed.
SubagentStop  (matcher odoo-master:.*): enforces the reporting contract — the final message must contain
              a `STATUS:` line; one re-prompt per subagent (stop_hook_active prevents loops). Statuses
              are logged to .odoo-master/logs/agent-status.jsonl.
SessionEnd:   appends a session summary (files changed, gate blocks, agent statuses) to logs/sessions.jsonl.
PostToolUse Bash (evidence capture): when `odoo-master validate` / `runtime test` ran, the output is stored
              as session evidence automatically (and attached to the single active execution, if any).
"""
from __future__ import annotations

import json
import re

from ..util import append_jsonl, now_iso, read_json, state_dir, write_json
from . import changed_files, out, project_root, safe_main, session_dir

STATUS_RE = re.compile(r"STATUS:\s*(DONE_WITH_CONCERNS|DONE|NEEDS_CONTEXT|BLOCKED)\b")


def _active(root) -> list[dict]:
    d = state_dir(root) / "executions"
    res = []
    for p in sorted(d.glob("*.json")) if d.exists() else []:
        ex = read_json(p) or {}
        if ex.get("status") in ("running", "waiting_approval", "blocked"):
            res.append({"id": ex["id"], "workflow": ex["workflow"], "ticket": ex.get("ticket"),
                        "running": [k for k, v in ex["steps"].items() if v["status"] == "RUNNING"]})
    return res


def subagent_start(payload: dict) -> int:
    agent = payload.get("agent_type") or ""
    if not agent.startswith("odoo-master:"):
        return 0
    root = project_root(payload)
    ver = read_json(state_dir(root) / "odoo-version.json") or {}
    act = _active(root)
    lines = [f"[odoo-master context for {agent}]",
             f"- Project root: {root}; Odoo series: {ver.get('version') or 'unknown'} (confidence {ver.get('confidence')})"
             + ("; CONFLICTING version signals — confirm before writing version-specific code" if ver.get("conflicts") else ""),
             "- Read ${CLAUDE_PLUGIN_ROOT}/instructions/global.md first; project facts in .odoo-master/project-context.md.",
             "- CLI: `odoo-master` (validate, runtime test, source grep/show, lookup, migration, evidence add).",
             "- End with `STATUS: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED`, then your structured output; cite path:line."]
    for e in act[:3]:
        lines.append(f"- Active execution {e['id']} ({e['workflow']}, ticket {e['ticket']}), running steps: {', '.join(e['running']) or '-'}")
    out({"hookSpecificOutput": {"hookEventName": "SubagentStart", "additionalContext": "\n".join(lines)}})
    return 0


def subagent_stop(payload: dict) -> int:
    agent = payload.get("agent_type") or ""
    if not agent.startswith("odoo-master:"):
        return 0
    root = project_root(payload)
    msg = payload.get("last_assistant_message") or ""
    m = STATUS_RE.search(msg)
    append_jsonl(state_dir(root) / "logs" / "agent-status.jsonl",
                 {"at": now_iso(), "session": payload.get("session_id"), "agent": agent, "agent_id": payload.get("agent_id"),
                  "status": m.group(1) if m else None})
    if m or payload.get("stop_hook_active"):
        return 0
    out({"decision": "block",
         "reason": "Finish with the odoo-master reporting contract: one line `STATUS: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED`, "
                   "then the structured output (findings with path:line, what was verified and what was not)."})
    return 0


def session_end(payload: dict) -> int:
    root = project_root(payload)
    sd = session_dir(payload)
    statuses = []
    log = state_dir(root) / "logs" / "agent-status.jsonl"
    if log.exists():
        for ln in log.read_text().splitlines():
            try:
                rec = json.loads(ln)
            except ValueError:
                continue
            if rec.get("session") == payload.get("session_id"):
                statuses.append(rec.get("status"))
    append_jsonl(state_dir(root) / "logs" / "sessions.jsonl", {
        "at": now_iso(), "session": payload.get("session_id"), "reason": payload.get("reason"),
        "files_changed": len(changed_files(payload)), "gate_blocks": (read_json(sd / "gate.json") or {}).get("blocks", 0),
        "agent_statuses": statuses, "active_executions": [e["id"] for e in _active(root)]})
    return 0


CAPTURE = re.compile(r"\bodoo-master\b(?:\s+--\S+(?:\s+\S+)?)*\s+(validate|runtime\s+test|migration\s+scan|db\s+overview)")


def evidence_capture(payload: dict) -> int:
    cmd = (payload.get("tool_input") or {}).get("command", "")
    m = CAPTURE.search(cmd)
    if not m:
        return 0
    resp = payload.get("tool_response")
    text = resp.get("stdout", "") if isinstance(resp, dict) else str(resp or "")
    if not text.strip():
        return 0
    root = project_root(payload)
    kind_map = {"validate": ("validation", "static"), "runtime test": ("runtime-test", "runtime"),
                "migration scan": ("migration-check", "static"), "db overview": ("database-check", "database")}
    key = re.sub(r"\s+", " ", m.group(1))
    kind, level = kind_map[key]
    status = "info"
    try:
        data = json.loads(text)
        if key == "validate":
            status = "passed" if data.get("passed") else "failed"
        elif key == "runtime test":
            status = {"passed": "passed", "failed": "failed", "error": "failed", "skipped": "skipped",
                      "passed_no_tests": "passed_no_tests"}.get(data.get("status"), "info")
    except ValueError:
        if key == "validate":
            em = re.search(r"errors=(\d+)", text)
            status = "passed" if em and em.group(1) == "0" else "failed" if em else "info"
    sid = (payload.get("session_id") or "unknown")[:40]
    act = _active(root)
    execution = act[0]["id"] if len(act) == 1 else f"session-{sid}"
    d = state_dir(root) / "evidence" / execution
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{kind}-{now_iso().replace(':', '')}.txt"
    f.write_text(f"$ {cmd}\n\n{text}", encoding="utf-8")
    from ..reporting.evidence import add
    add(execution, kind, level, str(f), root, summary=f"captured from: {cmd[:160]}", status=status, command=cmd[:300])
    write_json(session_dir(payload) / "last-evidence.json", {"execution": execution, "kind": kind, "status": status, "file": str(f)})
    return 0


def run_subagent_start() -> int:
    return safe_main(subagent_start)


def run_subagent_stop() -> int:
    return safe_main(subagent_stop)


def run_session_end() -> int:
    return safe_main(session_end)


def run_evidence_capture() -> int:
    return safe_main(evidence_capture)
