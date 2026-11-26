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
    sd = session_dir(payload)
    from .post_edit import finding_key
    baseline = (read_json(sd / "baseline.json") or {}).get("files", {})
    def preexisting(f):
        return finding_key(f, root) in set(baseline.get(f["file"], []))
    in_changed = [f for f in res["findings"] if f["severity"] in block_on and f["file"] in changed_rel]
    blocking = [f for f in in_changed if not preexisting(f)]
    other = [f for f in res["findings"] if f["severity"] == "error" and (f["file"] not in changed_rel or preexisting(f))]
    state = read_json(sd / "gate.json") or {"blocks": 0}
    write_json(sd / "last-validation.json", res)
    if not blocking:
        evidence_recorded = (sd / "last-evidence.json").exists()
        odoo_files = [f for f in changed_rel if f.endswith((".py", ".xml", ".csv", ".js"))]
        if odoo_files and not evidence_recorded and not state.get("verification_nudged") and gate.get("require_validation_run", True):
            state["verification_nudged"] = True
            write_json(sd / "gate.json", state)
            from ..util import PLUGIN_ROOT
            out({"decision": "block", "reason": (
                f"odoo-master: you changed Odoo files ({', '.join(odoo_files[:5])}) but no validation was run in this session. "
                f"Run `{PLUGIN_ROOT}/bin/odoo-master validate --files {' '.join(odoo_files[:5])} --brief` "
                "(and `runtime test --modules <m>` if Docker is available). Then give your complete final answer again: what you changed and why "
                "(root cause), and which verification levels ran and which did not.")})
            return 0
        if other:
            out({"systemMessage": f"odoo-master: {len(other)} pre-existing validation error(s) in the touched modules were not introduced this session "
                                  "(not blocking; mention them to the user if relevant)."})
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
