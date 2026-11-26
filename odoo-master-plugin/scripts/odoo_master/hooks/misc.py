"""Smaller hooks: PreCompact ledger, UserPromptSubmit reference detection, MCP call logging."""
from __future__ import annotations

import re

from ..util import append_jsonl, now_iso, read_json, redact_text, state_dir, write_json
from . import changed_files, out, project_root, safe_main, session_dir

JIRA_KEY = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d{1,6})\b")
GH_REF = re.compile(r"github\.com/([\w.-]+)/([\w.-]+)/(issues|pull)/(\d+)")
SLACK_LINK = re.compile(r"https://[\w-]+\.slack\.com/archives/(\w+)/p(\d+)")
LINEAR_LINK = re.compile(r"linear\.app/[\w-]+/issue/([A-Z]+-\d+)")


# --------------------------------------------------------------------------- PreCompact
def precompact(payload: dict) -> int:
    root = project_root(payload)
    sd = state_dir(root)
    active = []
    for p in sorted((sd / "executions").glob("*.json")) if (sd / "executions").exists() else []:
        ex = read_json(p) or {}
        if ex.get("status") in ("running", "waiting_approval", "blocked", "stalled"):
            active.append(f"{ex['id']} ({ex['workflow']}, ticket {ex.get('ticket')}, status {ex['status']})")
    files = changed_files(payload)
    ledger = ["# odoo-master session ledger", f"- at: {now_iso()}", f"- active executions: {', '.join(active) or 'none'}",
              f"- files changed this session: {len(files)}"] + [f"  - {f}" for f in files[:50]]
    (session_dir(payload) / "ledger.md").write_text("\n".join(ledger) + "\n", encoding="utf-8")
    # stdout of PreCompact becomes compaction instructions
    print("Preserve verbatim: workflow execution ids, ticket ids/URLs, approval records (who/when), the detected Odoo version, "
          "branch names, unresolved findings, and which verification levels were actually executed vs. missing. "
          f"Active executions: {', '.join(active) or 'none'}.")
    return 0


# --------------------------------------------------------------------------- UserPromptSubmit
INTENT_HINTS = [
    (re.compile(r"\b(estimate|estimation|how long|effort|plan)\b", re.I),
     "planning: write the plan from templates/architecture/technical-plan.md and compute the estimate with `{cli} estimate --input <tasks.json> --out .odoo-master/estimates/<slug>` (do not estimate by hand); /odoo-master:plan does both"),
    (re.compile(r"\b(fix|bug|error|traceback|broken|fails?|crash)\b", re.I),
     "bug fix: reproduce, root-cause with path:line, fix, then `{cli} validate --brief` and `{cli} runtime test --modules <m>` when Docker is available"),
    (re.compile(r"\b(migrat\w*|upgrad\w*|port(ing)?)\b", re.I),
     "migration: `{cli} migration plan --from <src> --to <dst>`, then `{cli} source upgrade-code` (dry run) per hop"),
    (re.compile(r"\b(new module|create (a |an )?module|scaffold)\b", re.I),
     "new module: check the reuse ladder first, then `{cli} scaffold <name> --model <x.y> --depends <a,b>`"),
]
VERSION_IN_PROMPT = re.compile(r"\bodoo\s*(1[4-9]|2\d)(?:\.0)?\b", re.I)


def prompt(payload: dict) -> int:
    text = payload.get("prompt") or ""
    refs = []
    for m in GH_REF.finditer(text):
        refs.append(f"GitHub {'PR' if m.group(3) == 'pull' else 'issue'} {m.group(1)}/{m.group(2)}#{m.group(4)}")
    for m in SLACK_LINK.finditer(text):
        refs.append(f"Slack thread channel={m.group(1)} ts={m.group(2)[:10]}.{m.group(2)[10:]}")
    for m in LINEAR_LINK.finditer(text):
        refs.append(f"Linear issue {m.group(1)}")
    keys = [k for k in JIRA_KEY.findall(text) if not k.startswith(("UTF-", "ISO-", "SHA-", "HTTP-", "RFC-"))]
    refs += [f"ticket key {k}" for k in dict.fromkeys(keys)]
    root = project_root(payload)
    ver = read_json(state_dir(root, create=False) / "odoo-version.json") or {}
    hints = []
    if ver.get("version") or ver.get("conflicts"):
        from ..util import PLUGIN_ROOT
        cli = f"{PLUGIN_ROOT}/bin/odoo-master"
        hints = [h.format(cli=cli) for rx, h in INTENT_HINTS if rx.search(text)][:2]
        named = sorted({f"{v}.0" for v in VERSION_IN_PROMPT.findall(text)})
        if ver.get("conflicts") and len(named) == 1:
            # The user stated the target series in their own words: record it (hooks run outside the Bash sandbox).
            from ..odoo.version import confirm
            try:
                confirm(root, named[0])
                hints.insert(0, f"version signals conflicted; the prompt names Odoo {named[0]}, so it was recorded as the confirmed target "
                                f"series (`{cli} detect-version --confirm` changes it). Write {named[0]}-correct code")
            except (ValueError, OSError) as exc:
                hints.insert(0, f"version signals conflict and the prompt names Odoo {named[0]}; record it with "
                                f"`{cli} detect-version --confirm {named[0]}` ({exc})")
        elif ver.get("conflicts"):
            hints.insert(0, "the project's Odoo version signals conflict: ask the user which series is targeted before editing module code")
    if not refs and not hints:
        return 0
    if not refs:
        out({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                    "additionalContext": "[odoo-master] " + "; ".join(hints)}})
        return 0
    reg = read_json(state_dir(project_root(payload)) / "mcp-registry.json") or {}
    providers = sorted({s.get("provider") for s in (reg.get("servers") or {}).values() if s.get("provider")})
    ctx = (f"[odoo-master] Detected references: {'; '.join(refs[:6])}. Keep the original ticket/thread id on every artifact and update; "
           f"never act on an unrelated ticket. Registered integration providers: {', '.join(providers) or 'none yet — run /odoo-master:mcp-integration to discover'}. "
           "Ticket work: /odoo-master:jira-management; Slack reports: /odoo-master:slack-triage; GitHub: /odoo-master:github-management."
           + (" Also: " + "; ".join(hints) if hints else ""))
    out({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": ctx}})
    return 0


# --------------------------------------------------------------------------- MCP logging
def _mcp_record(payload: dict, ok: bool) -> dict:
    name = payload.get("tool_name", "")
    parts = name.split("__")
    server = (payload.get("mcp_server") or {}).get("name") or (parts[1] if len(parts) > 2 else None)
    rec = {"at": now_iso(), "session": payload.get("session_id"), "tool": name, "server": server, "ok": ok,
           "duration_ms": payload.get("duration_ms")}
    if not ok:
        resp = payload.get("tool_response") or payload.get("error") or ""
        rec["error"] = redact_text(str(resp))[:300]
    return rec


def mcp_post(payload: dict) -> int:
    append_jsonl(state_dir(project_root(payload)) / "logs" / "mcp-calls.jsonl", _mcp_record(payload, True))
    return 0


def mcp_failure(payload: dict) -> int:
    root = project_root(payload)
    rec = _mcp_record(payload, False)
    append_jsonl(state_dir(root) / "logs" / "mcp-calls.jsonl", rec)
    reg_path = state_dir(root) / "mcp-registry.json"
    reg = read_json(reg_path)
    if reg and rec["server"] in (reg.get("servers") or {}):
        reg["servers"][rec["server"]]["last_failure"] = {"at": rec["at"], "tool": rec["tool"], "error": rec.get("error")}
        write_json(reg_path, reg)
    out({"hookSpecificOutput": {"hookEventName": "PostToolUseFailure", "additionalContext":
        f"[odoo-master] MCP tool {rec['tool']} failed: {rec.get('error', '')[:200]}. If it is an auth/connection problem, tell the user to "
        "reconnect it (/mcp) and continue with what can be done without it; retry read-only calls once; never blindly retry write calls "
        "(check whether the first attempt took effect)."}})
    return 0


def run_precompact() -> int:
    return safe_main(precompact)


def run_prompt() -> int:
    return safe_main(prompt)


def run_mcp_post() -> int:
    return safe_main(mcp_post)


def run_mcp_failure() -> int:
    return safe_main(mcp_failure)
