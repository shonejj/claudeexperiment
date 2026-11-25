"""Workflow engine.

A workflow (workflows/*.yaml, validated by schemas/workflow.schema.json) is a DAG of steps:
  type: task       an agent does work (agent, skills, instructions, outputs)
  type: approval   a gate: a human (or, in autonomous mode under policy, the engine) approves or rejects
  type: notify     post an update to the originating system (ticket/chat) through an MCP capability
Ordering comes from `needs`; every step whose needs are satisfied is returned together by
`next_steps` -> parallel execution. `when` conditions skip steps. Failures retry up to `retries`,
then follow `on_failure` (fail | continue | {retry_from: <step>, max_loops: N}) — the bounded repair loop.

The execution record (.odoo-master/executions/<id>.json, schemas/execution.schema.json) is the
checkpoint: every transition is written atomically and appended to <id>.events.jsonl, so a session
can resume after compaction, restart or handoff with `status` / `next`.
"""
from __future__ import annotations

import datetime as dt
import secrets
from pathlib import Path

from ..config import load_config, policy
from ..util import PLUGIN_ROOT, append_jsonl, load_yaml, now_iso, read_json, state_dir, write_json
from .expr import evaluate

DONE_STATES = {"DONE", "DONE_WITH_CONCERNS", "SKIPPED", "APPROVED"}
TERMINAL_FAIL = {"FAILED", "REJECTED", "TIMED_OUT", "CANCELLED"}
RISK_ORDER = ["low", "medium", "high", "critical"]


def workflows_dir() -> Path:
    return PLUGIN_ROOT / "workflows"


def project_workflows_dir(root: Path | None = None) -> Path:
    return state_dir(root, create=False) / "workflows"


def load_definition(name: str, root: Path | None = None) -> dict:
    for d in (project_workflows_dir(root), workflows_dir()):
        p = d / f"{name}.yaml"
        if p.exists():
            data = load_yaml(p)
            data["_source"] = str(p)
            return data
    raise FileNotFoundError(f"workflow '{name}' not found")


def list_workflows(root: Path | None = None) -> list[dict]:
    seen, out = set(), []
    for d in (project_workflows_dir(root), workflows_dir()):
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.yaml")):
            if p.stem in seen:
                continue
            seen.add(p.stem)
            w = load_yaml(p)
            out.append({"name": w.get("name"), "version": w.get("version"), "description": w.get("description"),
                        "steps": len(w.get("steps", [])), "triggers": w.get("triggers", []), "source": str(p)})
    return out


def validate_definition(wf: dict) -> dict:
    from ..schemas import validate_data
    res = validate_data("workflow", {k: v for k, v in wf.items() if not k.startswith("_")})
    errors = list(res["errors"])
    ids = [s.get("id") for s in wf.get("steps", [])]
    if len(ids) != len(set(ids)):
        errors.append("duplicate step ids")
    idset = set(ids)
    for s in wf.get("steps", []):
        for n in s.get("needs", []) or []:
            if n not in idset:
                errors.append(f"step {s.get('id')}: needs unknown step {n}")
        of = s.get("on_failure")
        if isinstance(of, dict) and of.get("retry_from") not in idset:
            errors.append(f"step {s.get('id')}: retry_from unknown step {of.get('retry_from')}")
        for key in ("when", "auto_approve_when"):
            if s.get(key):
                try:
                    evaluate(s[key], ctx={}, inputs={}, config={})
                except ValueError as exc:
                    errors.append(f"step {s.get('id')}: invalid {key}: {exc}")
                except Exception:
                    pass  # runtime KeyError etc. are fine at validation time
        agent = s.get("agent")
        if agent and not (PLUGIN_ROOT / "agents" / f"{agent}.md").exists():
            errors.append(f"step {s.get('id')}: agent '{agent}' has no agents/{agent}.md")
        for sk in s.get("skills", []) or []:
            if not (PLUGIN_ROOT / "skills" / sk / "SKILL.md").exists():
                errors.append(f"step {s.get('id')}: skill '{sk}' has no skills/{sk}/SKILL.md")
    # cycle check
    graph = {s["id"]: s.get("needs", []) or [] for s in wf.get("steps", []) if "id" in s}
    state: dict[str, int] = {}

    def visit(n):
        if state.get(n) == 1:
            raise ValueError(n)
        if state.get(n) == 2:
            return
        state[n] = 1
        for m in graph.get(n, []):
            visit(m)
        state[n] = 2
    try:
        for n in graph:
            visit(n)
    except ValueError as exc:
        errors.append(f"dependency cycle through step {exc}")
    return {"name": wf.get("name"), "valid": not errors, "errors": errors}


def validate_all() -> dict:
    return {p.stem: validate_definition(load_yaml(p)) for p in sorted(workflows_dir().glob("*.yaml"))}


# ----------------------------------------------------------------------------- executions
def _exec_path(root, eid) -> Path:
    return state_dir(root) / "executions" / f"{eid}.json"


def _load(eid, root) -> dict:
    ex = read_json(_exec_path(root, eid))
    if not ex:
        raise FileNotFoundError(f"execution {eid} not found")
    return ex


def _save(ex, root, event: dict | None = None) -> dict:
    ex["updated_at"] = now_iso()
    write_json(_exec_path(root, ex["id"]), ex)
    if event:
        append_jsonl(state_dir(root) / "executions" / f"{ex['id']}.events.jsonl", {"at": ex["updated_at"], **event})
    return ex


def start(name: str, inputs: dict, root: Path | None = None, ticket: str | None = None, source_event: dict | None = None) -> dict:
    wf = load_definition(name, root)
    v = validate_definition(wf)
    if not v["valid"]:
        raise ValueError(f"workflow {name} is invalid: {v['errors']}")
    for k, spec in (wf.get("inputs") or {}).items():
        if (spec or {}).get("required") and k not in inputs:
            raise ValueError(f"missing required input '{k}'")
        if k not in inputs and (spec or {}).get("default") is not None:
            inputs[k] = spec["default"]
    cfg = load_config(root)
    eid = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)
    ex = {
        "schema_version": 1, "id": eid, "workflow": name, "workflow_version": wf.get("version"),
        "workflow_source": wf["_source"], "status": "running", "created_at": now_iso(),
        "autonomy": cfg.get("autonomy", "checkpoint"), "inputs": inputs, "ticket": ticket or inputs.get("ticket"),
        "source_event": source_event, "context": {"risk": inputs.get("risk", "medium")},
        "steps": {s["id"]: {"status": "PENDING", "attempts": 0, "loops": 0} for s in wf["steps"]},
        "approvals": [], "evidence": [],
    }
    _save(ex, root, {"type": "started", "workflow": name, "ticket": ex["ticket"]})
    return next_steps(eid, root)


def _step_defs(ex) -> dict:
    wf = load_yaml(ex["workflow_source"])
    return {s["id"]: s for s in wf["steps"]}, wf


def _risk_leq(a: str, b: str) -> bool:
    try:
        return RISK_ORDER.index(a) <= RISK_ORDER.index(b)
    except ValueError:
        return False


def next_steps(eid: str, root: Path | None = None) -> dict:
    ex = _load(eid, root)
    if ex["status"] not in ("running", "waiting_approval"):
        return {"execution": eid, "status": ex["status"], "ready": [], "message": "execution is not active"}
    defs, wf = _step_defs(ex)
    now = dt.datetime.now(dt.timezone.utc)
    changed = True
    events = []
    cfg = load_config(root)
    appr_policy = policy(cfg, "approvals")
    while changed:
        changed = False
        for sid, sd in defs.items():
            st = ex["steps"][sid]
            # timeouts for running steps
            if st["status"] == "RUNNING" and st.get("deadline") and dt.datetime.fromisoformat(st["deadline"]) < now:
                events.append({"type": "timeout", "step": sid})
                _fail_step(ex, sid, sd, "TIMED_OUT", defs)
                changed = True
                continue
            if st["status"] != "PENDING":
                continue
            needs = sd.get("needs", []) or []
            if any(ex["steps"][n]["status"] in TERMINAL_FAIL for n in needs) and sd.get("type") != "notify":
                st["status"] = "SKIPPED"
                st["reason"] = "upstream failed"
                changed = True
                continue
            if not all(ex["steps"][n]["status"] in DONE_STATES for n in needs):
                continue
            try:
                ok = evaluate(sd.get("when"), ctx=ex["context"], inputs=ex["inputs"], config=cfg)
            except Exception as exc:  # noqa: BLE001
                ok = False
                st["reason"] = f"condition error: {exc}"
            if not ok:
                st["status"] = "SKIPPED"
                st.setdefault("reason", "condition false")
                changed = True
                continue
            if sd.get("type") == "approval":
                risk = ex["context"].get("risk", "medium")
                threshold = (appr_policy.get("autonomous") or {}).get("max_auto_approve_risk", "low")
                always_human = sd.get("always_human") or risk in (appr_policy.get("always_human_risks") or ["critical"])
                auto = (ex["autonomy"] == "autonomous" and not always_human and _risk_leq(risk, threshold)
                        and evaluate(sd.get("auto_approve_when", True), ctx=ex["context"], inputs=ex["inputs"], config=cfg))
                if auto:
                    st["status"] = "APPROVED"
                    ex["approvals"].append({"step": sid, "decision": "approved", "by": "policy:autonomous", "at": now_iso(),
                                            "risk": risk, "threshold": threshold})
                    events.append({"type": "auto_approved", "step": sid, "risk": risk})
                else:
                    st["status"] = "WAITING_APPROVAL"
                    st["requested_at"] = now_iso()
                    events.append({"type": "approval_requested", "step": sid, "risk": risk})
                changed = True
            else:
                st["status"] = "READY"
                changed = True
    ready, waiting = [], []
    for sid, sd in defs.items():
        st = ex["steps"][sid]
        if st["status"] == "READY":
            st["status"] = "RUNNING"
            st["attempts"] += 1
            st["started_at"] = now_iso()
            tmo = sd.get("timeout_minutes") or (wf.get("defaults") or {}).get("timeout_minutes")
            if tmo:
                st["deadline"] = (now + dt.timedelta(minutes=int(tmo))).isoformat()
            events.append({"type": "dispatched", "step": sid, "attempt": st["attempts"]})
        if st["status"] == "RUNNING":
            ready.append(_brief(sid, sd, st, ex))
        elif st["status"] == "WAITING_APPROVAL":
            waiting.append({"step": sid, "approvers": sd.get("approvers"), "instructions": sd.get("instructions"),
                            "risk": ex["context"].get("risk"), "present": sd.get("present", [])})
    statuses = {s["status"] for s in ex["steps"].values()}
    if not ready and not waiting:
        if statuses & {"FAILED", "TIMED_OUT"}:
            ex["status"] = "failed"
        elif "REJECTED" in statuses:
            ex["status"] = "rejected"
        elif statuses <= DONE_STATES | {"PENDING"} and "PENDING" not in statuses:
            ex["status"] = "completed"
        elif "PENDING" in statuses:
            ex["status"] = "stalled"
    else:
        ex["status"] = "waiting_approval" if waiting and not ready else "running"
    for e in events:
        _save(ex, root, e)
    _save(ex, root)
    return {"execution": eid, "workflow": ex["workflow"], "status": ex["status"], "ticket": ex.get("ticket"),
            "ready": ready, "waiting_approval": waiting,
            "progress": {k: v["status"] for k, v in ex["steps"].items()}}


def _brief(sid, sd, st, ex) -> dict:
    return {"step": sid, "type": sd.get("type", "task"), "agent": sd.get("agent"), "skills": sd.get("skills", []),
            "capability": sd.get("capability"), "attempt": st["attempts"], "instructions": sd.get("instructions"),
            "outputs": sd.get("outputs", []), "evidence": sd.get("evidence", []), "parallel_with": sd.get("parallel_group"),
            "context_keys": sorted(ex["context"].keys())}


def _fail_step(ex, sid, sd, status, defs):
    st = ex["steps"][sid]
    retries = int(sd.get("retries", 0))
    if st["attempts"] <= retries:
        st["status"] = "PENDING"
        st["last_failure"] = status
        return "retry"
    of = sd.get("on_failure", "fail")
    if isinstance(of, dict) and of.get("retry_from"):
        maxl = int(of.get("max_loops", 2))
        if st["loops"] < maxl:
            st["loops"] += 1
            _reset_from(ex, of["retry_from"], defs, keep=sid)
            st["status"] = "PENDING"
            st["attempts"] = 0
            return "loop"
        st["status"] = "FAILED"
        return "loop_exhausted"
    if of == "continue":
        st["status"] = "DONE_WITH_CONCERNS"
        st["reason"] = f"{status} (on_failure: continue)"
        return "continue"
    st["status"] = status if status != "FAILED" else "FAILED"
    return "fail"


def _reset_from(ex, start_id, defs, keep=None):
    """Reset start step and everything downstream of it to PENDING (repair loop)."""
    downstream = {start_id}
    changed = True
    while changed:
        changed = False
        for sid, sd in defs.items():
            if sid not in downstream and set(sd.get("needs", []) or []) & downstream:
                downstream.add(sid)
                changed = True
    for sid in downstream:
        if sid == keep:
            continue
        loops = ex["steps"][sid].get("loops", 0)
        ex["steps"][sid] = {"status": "PENDING", "attempts": 0, "loops": loops}


def complete(eid: str, step: str, status: str, output: dict | None, root: Path | None = None, note: str | None = None) -> dict:
    status = status.upper()
    allowed = {"DONE", "DONE_WITH_CONCERNS", "NEEDS_CONTEXT", "BLOCKED", "FAILED"}
    if status not in allowed:
        raise ValueError(f"status must be one of {sorted(allowed)}")
    ex = _load(eid, root)
    defs, _ = _step_defs(ex)
    if step not in defs:
        raise KeyError(f"unknown step {step}")
    st = ex["steps"][step]
    if st["status"] != "RUNNING":
        raise ValueError(f"step {step} is {st['status']}, not RUNNING")
    output = output or {}
    st["finished_at"] = now_iso()
    st["note"] = note
    outcome = status
    if status in ("DONE", "DONE_WITH_CONCERNS"):
        st["status"] = status
        ex["context"][step] = output
        for key in defs[step].get("outputs", []) or []:
            if key in output:
                ex["context"][key] = output[key]
        if "risk" in output and output["risk"] in RISK_ORDER:
            ex["context"]["risk"] = output["risk"]
    elif status in ("NEEDS_CONTEXT", "BLOCKED"):
        st["status"] = "PENDING"  # re-dispatched after the orchestrator supplies context (workflow set)
        st["attempts"] = max(0, st["attempts"] - 1)
        st["blocked_reason"] = note or output.get("reason")
        ex["status"] = "blocked" if status == "BLOCKED" else ex["status"]
    else:
        outcome = _fail_step(ex, step, defs[step], "FAILED", defs)
        st["last_error"] = note or output.get("error")
    _save(ex, root, {"type": "step_completed", "step": step, "status": status, "outcome": outcome, "note": note})
    if status == "BLOCKED":
        return {"execution": eid, "status": "blocked", "step": step, "reason": st["blocked_reason"],
                "hint": "Resolve the blocker, then `workflow set` context and `workflow next` to resume."}
    if ex["status"] == "blocked":
        ex["status"] = "running"
        _save(ex, root)
    return next_steps(eid, root)


def approve(eid: str, step: str, by: str, root: Path | None = None, decision: str = "approved", note: str | None = None) -> dict:
    if not by:
        raise ValueError("--by is required: record who approved (name, ticket comment URL, or chat message link)")
    ex = _load(eid, root)
    st = ex["steps"].get(step)
    if not st or st["status"] != "WAITING_APPROVAL":
        raise ValueError(f"step {step} is not waiting for approval")
    defs, _ = _step_defs(ex)
    st["status"] = "APPROVED" if decision == "approved" else "REJECTED"
    ex["approvals"].append({"step": step, "decision": decision, "by": by, "at": now_iso(), "note": note,
                            "risk": ex["context"].get("risk")})
    if decision != "approved":
        on_reject = defs[step].get("on_reject")
        if on_reject:
            _reset_from(ex, on_reject, defs)
            st["status"] = "PENDING"
            ex["status"] = "running"
            ex["context"]["rejection_feedback"] = note
    else:
        ex["status"] = "running"
    _save(ex, root, {"type": "approval", "step": step, "decision": decision, "by": by})
    return next_steps(eid, root)


def set_context(eid: str, values: dict, root: Path | None = None) -> dict:
    ex = _load(eid, root)
    for k, v in values.items():
        ex["context"][k] = v
    if ex["status"] == "blocked":
        ex["status"] = "running"
    _save(ex, root, {"type": "context_set", "keys": list(values)})
    return {"execution": eid, "context": ex["context"]}


def status(eid: str, root: Path | None = None) -> dict:
    ex = _load(eid, root)
    return {k: ex[k] for k in ("id", "workflow", "status", "ticket", "autonomy", "inputs", "approvals", "created_at", "updated_at")} | {
        "steps": ex["steps"], "context_keys": sorted(ex["context"].keys()), "risk": ex["context"].get("risk")}


def cancel(eid: str, root: Path | None = None, reason: str | None = None) -> dict:
    ex = _load(eid, root)
    for st in ex["steps"].values():
        if st["status"] in ("PENDING", "RUNNING", "READY", "WAITING_APPROVAL"):
            st["status"] = "CANCELLED"
    ex["status"] = "cancelled"
    _save(ex, root, {"type": "cancelled", "reason": reason})
    return {"execution": eid, "status": "cancelled"}


def list_executions(root: Path | None = None) -> list[dict]:
    d = state_dir(root) / "executions"
    out = []
    for p in sorted(d.glob("*.json")) if d.exists() else []:
        ex = read_json(p) or {}
        out.append({"id": ex.get("id"), "workflow": ex.get("workflow"), "status": ex.get("status"), "ticket": ex.get("ticket"),
                    "updated_at": ex.get("updated_at")})
    return out
