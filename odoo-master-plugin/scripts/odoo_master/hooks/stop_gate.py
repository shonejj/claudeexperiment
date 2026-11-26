"""Stop hook: quality gate over the Odoo modules changed in this session (taste-skill style gate).

Blocks finishing while static validation errors remain in changed modules, at most
policies/testing.yaml quality_gate.max_blocks_per_session times; after that it reports instead.
"""
from __future__ import annotations

from pathlib import Path

from ..config import load_config, policy
from ..util import read_json, state_dir, write_json
from . import changed_files, out, project_root, safe_main, session_dir


def main(payload: dict) -> int:
    root = project_root(payload)
    cfg = load_config(root)
    gate = policy(cfg, "testing").get("quality_gate", {})
    if not gate.get("enabled", True):
        return 0
    files = [f for f in changed_files(payload) if Path(f).exists()]
    if not files:
        return 0
    from ..odoo.validate import validate
    series = (read_json(state_dir(root, create=False) / "odoo-version.json") or {}).get("version")
    res = validate(root, series=series, files=files, with_js=True)
    if not res["modules_checked"]:
        return 0
    changed_rel = set()
    for f in files:
        try:
            changed_rel.add(str(Path(f).resolve().relative_to(root)))
        except ValueError:
            pass
    block_on = set(gate.get("block_on", ["error"]))
    # Only findings in files touched this session (pre-existing issues elsewhere are reported, not blocking)
    blocking = [f for f in res["findings"] if f["severity"] in block_on and f["file"] in changed_rel]
    other = [f for f in res["findings"] if f["severity"] == "error" and f["file"] not in changed_rel]
    sd = session_dir(payload)
    state = read_json(sd / "gate.json") or {"blocks": 0}
    write_json(sd / "last-validation.json", res)
    if not blocking:
        if other:
            out({"systemMessage": f"odoo-master: {len(other)} pre-existing validation error(s) in changed modules (not introduced in files edited this session)."})
        return 0
    if state["blocks"] >= int(gate.get("max_blocks_per_session", 3)):
        out({"systemMessage": f"odoo-master quality gate: {len(blocking)} error(s) remain after {state['blocks']} attempts — report them as unresolved."})
        return 0
    state["blocks"] += 1
    write_json(sd / "gate.json", state)
    lines = [f"odoo-master quality gate ({state['blocks']}/{gate.get('max_blocks_per_session', 3)}): fix these errors in files you changed before finishing, "
             "or explain why they are intentional:"]
    for f in blocking[:12]:
        lines.append(f"- {f['file']}:{f['line'] or '?'} [{f['rule']}] {f['message']}")
    out({"decision": "block", "reason": "\n".join(lines)})
    return 0


def run() -> int:
    return safe_main(main)
