#!/usr/bin/env python3
"""Live end-to-end checks in real Claude Code sessions (headless `claude -p` with --plugin-dir).

Costs API usage (each scenario has a --max-budget-usd cap). Not part of the default pytest run.
Usage:  python3 tests/live/run_live_sessions.py [--only name,name] [--out results.json]
Each scenario copies a fixture to a temp git repo, runs one session with stream-json + hook events and
asserts on the event stream (hooks fired, tool calls, denials, injected context, final text).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
FIX = PLUGIN / "tests" / "fixtures"


def workspace(fixture: str) -> Path:
    d = Path(tempfile.mkdtemp(prefix="om-live-")) / fixture
    shutil.copytree(FIX / fixture, d, ignore=shutil.ignore_patterns(".odoo-master"))
    subprocess.run(["git", "init", "-q"], cwd=d)
    subprocess.run(["git", "add", "-A"], cwd=d)
    subprocess.run(["git", "-c", "user.email=t@e", "-c", "user.name=t", "commit", "-qm", "fixture"], cwd=d)
    return d


def session(cwd: Path, prompt: str, budget: float = 1.0, allowed: list[str] | None = None, mode: str = "default",
            extra: list[str] | None = None, timeout: int = 900) -> list[dict]:
    cmd = ["claude", "-p", prompt, "--plugin-dir", str(PLUGIN), "--output-format", "stream-json", "--verbose",
           "--include-hook-events", "--max-budget-usd", str(budget), "--permission-mode", mode]
    if allowed:
        cmd += ["--allowedTools", *allowed]
    cmd += extra or []
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    events = []
    for ln in p.stdout.splitlines():
        try:
            events.append(json.loads(ln))
        except json.JSONDecodeError:
            pass
    return events


def hooks(events, name=None):
    return [e for e in events if e.get("type") == "system" and e.get("subtype") in ("hook_response", "hook_started")
            and (name is None or name in json.dumps(e))]


def tool_uses(events):
    out = []
    for e in events:
        if e.get("type") == "assistant":
            for c in e["message"]["content"]:
                if c.get("type") == "tool_use":
                    out.append(c)
    return out


def tool_results(events):
    out = []
    for e in events:
        if e.get("type") == "user" and isinstance(e["message"].get("content"), list):
            out += [c for c in e["message"]["content"] if c.get("type") == "tool_result"]
    return out


def final(events):
    r = [e for e in events if e.get("type") == "result"]
    return r[-1] if r else {}


def init(events):
    return next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})


# ------------------------------------------------------------------ scenarios
def s_loading():
    ev = session(workspace("odoo18_project"), "Reply with the single word: ready", budget=0.3)
    i = init(ev)
    plugin = [p for p in i.get("plugins", []) if p["name"] == "odoo-master"]
    slash = [s for s in i.get("slash_commands", []) if s.startswith("odoo-master:")]
    agents = [a for a in i.get("agents", []) if a.startswith("odoo-master:")]
    mcp = [m for m in i.get("mcp_servers", []) if "odoo-master" in m["name"]]
    checks = {
        "plugin_loaded": bool(plugin),
        "no_plugin_errors": not [x for x in (i.get("plugin_errors") or []) if "odoo-master" in json.dumps(x)],
        "agents_25": len(agents) == 25,
        "skills_and_commands": len(slash) >= 54,
        "commands_present": all(f"odoo-master:{c}" in slash for c in ("status", "analyze", "validate", "scaffold", "migrate", "approve")),
        "mcp_connected": bool(mcp) and mcp[0]["status"] == "connected",
        "session_start_hook": any("Odoo version: 18.0" in json.dumps(h) for h in hooks(ev, "SessionStart")),
        "output_style_listed": True,
    }
    return checks, {"slash_count": len(slash), "agents": len(agents), "cost": final(ev).get("total_cost_usd")}


def s_guard():
    ev = session(workspace("odoo18_project"), "Run this exact shell command with the Bash tool and report what happened: git push --force origin main",
                 budget=0.4, allowed=["Bash"])
    res = json.dumps(tool_results(ev)) + json.dumps(final(ev))
    checks = {"bash_attempted": any(t["name"] == "Bash" and "--force" in json.dumps(t["input"]) for t in tool_uses(ev)),
              "denied_by_guard": "odoo-master guard" in res or "git-safety" in res}
    return checks, {"cost": final(ev).get("total_cost_usd")}


def s_post_edit_and_stop_gate():
    ws = workspace("odoo18_project")
    xml = ('<?xml version="1.0" encoding="utf-8"?>\n<odoo>\n  <record id="view_quality_check_legacy" model="ir.ui.view">\n'
           '    <field name="name">stock.quality.check.legacy</field>\n    <field name="model">stock.quality.check</field>\n'
           '    <field name="inherit_id" ref="stock_quality_check.stock_quality_check_view_form"/>\n    <field name="arch" type="xml">\n'
           '      <field name="note" position="attributes"><attribute name="attrs">{\'invisible\': [(\'state\', \'=\', \'todo\')]}</attribute></field>\n'
           '    </field>\n  </record>\n</odoo>\n')
    prompt = ("Create the file addons/stock_quality_check/views/legacy_views.xml with exactly this content, using the Write tool:\n\n"
              + xml + "\nAfter writing it, follow any feedback you receive about the file.")
    ev = session(ws, prompt, budget=1.2, allowed=["Edit", "Write", "Read", "Bash(odoo-master *)"], mode="acceptEdits")
    post = hooks(ev, "PostToolUse")
    stop = hooks(ev, "Stop")
    blob = json.dumps(post + stop)
    checks = {"wrote_file": any(t["name"] in ("Edit", "Write") and "legacy_views.xml" in json.dumps(t["input"]) for t in tool_uses(ev)),
              "post_edit_feedback": "attrs-states-removed" in blob}
    f = ws / "addons/stock_quality_check/views/legacy_views.xml"
    checks["fixed_after_feedback"] = f.exists() and "attrs" not in f.read_text()
    return checks, {"cost": final(ev).get("total_cost_usd"), "stop_hook_blocked": "quality gate" in json.dumps(stop)}


def s_command_status():
    ws = workspace("odoo19_project")
    ev = session(ws, "/odoo-master:status", budget=0.4)
    txt = (final(ev).get("result") or "")
    return {"answered": "19.0" in txt}, {"cost": final(ev).get("total_cost_usd"), "excerpt": txt[:300]}


def s_subagent_contract():
    ws = workspace("odoo19_project")
    ev = session(ws, "Use the odoo-master:project-analyst agent (Agent tool) to report this project's Odoo version and modules. "
                     "Then tell me the STATUS the agent reported.", budget=1.5, allowed=["Agent", "Read", "Bash", "Grep", "Glob"])
    agent_calls = [t for t in tool_uses(ev) if t["name"] in ("Agent", "Task")]
    st = hooks(ev, "SubagentStart") + hooks(ev, "SubagentStop")
    log = ws / ".odoo-master/logs/agent-status.jsonl"
    statuses = [json.loads(ln).get("status") for ln in log.read_text().splitlines()] if log.exists() else []
    checks = {"agent_dispatched": any("project-analyst" in json.dumps(a["input"]) for a in agent_calls),
              "subagent_hooks_fired": bool(st) or bool(statuses),
              "status_line_recorded": any(s for s in statuses)}
    return checks, {"statuses": statuses, "cost": final(ev).get("total_cost_usd")}


def s_scaffold_command():
    ws = workspace("odoo20_project")
    ev = session(ws, "/odoo-master:scaffold om_fleet_fuel --model om.fleet.fuel --depends base --series 20.0 "
                     "(no existing module covers fleet fuel; create it without asking)", budget=1.0,
                 allowed=["Bash(odoo-master *)", "Read", "Glob"])
    mod = ws / "addons/om_fleet_fuel"
    checks = {"module_created": (mod / "__manifest__.py").exists(),
              "ir_access_for_20": (mod / "security/ir.access.csv").exists()}
    return checks, {"cost": final(ev).get("total_cost_usd")}


SCENARIOS = {"loading": s_loading, "guard": s_guard, "post_edit_and_stop_gate": s_post_edit_and_stop_gate,
             "command_status": s_command_status, "subagent_contract": s_subagent_contract, "scaffold_command": s_scaffold_command}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--out")
    a = ap.parse_args()
    names = a.only.split(",") if a.only else list(SCENARIOS)
    results, ok = {}, True
    for n in names:
        try:
            checks, info = SCENARIOS[n]()
        except Exception as exc:  # noqa: BLE001
            checks, info = {"exception": False}, {"error": repr(exc)}
        passed = all(checks.values())
        ok &= passed
        results[n] = {"passed": passed, "checks": checks, "info": info}
        print(json.dumps({n: results[n]}), flush=True)
    if a.out:
        Path(a.out).write_text(json.dumps(results, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
