"""PostToolUse (Edit|Write|MultiEdit): fast per-file Odoo validation + change ledger.

Findings are returned as additionalContext so Claude fixes them immediately; the hook never blocks.
"""
from __future__ import annotations

from pathlib import Path

from . import out, project_root, record_changed, safe_main
from ..util import read_json, state_dir

ODOO_SUFFIXES = (".py", ".xml", ".csv", ".js")


def _module_of(path: Path) -> Path | None:
    for anc in path.parents:
        if (anc / "__manifest__.py").exists():
            return anc
    return None


def main(payload: dict) -> int:
    ti = payload.get("tool_input") or {}
    fp = ti.get("file_path")
    if not fp:
        return 0
    root = project_root(payload)
    path = Path(fp).resolve()
    record_changed(payload, str(path))
    if path.suffix not in ODOO_SUFFIXES and path.name != "__manifest__.py":
        return 0
    mod = _module_of(path)
    if not mod or not path.exists():
        return 0
    from ..odoo import dependency_closure
    from ..odoo.inventory import parse_manifest, scan_module
    from ..odoo.validate import check_manifest, check_python, check_xml, check_version_rules
    series = (read_json(state_dir(root, create=False) / "odoo-version.json") or {}).get("version")
    findings = []
    if path.name == "__manifest__.py":
        f, _ = check_manifest(mod, root, series, {mod.name})
        findings += f
    elif path.suffix == ".py":
        findings += check_python(path, root)
    elif path.suffix == ".xml":
        manifest, _ = parse_manifest(mod / "__manifest__.py")
        deps = dependency_closure((manifest or {}).get("depends") or [], series)
        local = set(scan_module(mod, root)["xml_ids"])
        findings += check_xml(path, root, mod.name, deps, local)
    rel = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    findings += [f for f in check_version_rules(mod, root, series) if f["file"] == rel]
    errors = [f for f in findings if f["severity"] == "error"]
    warns = [f for f in findings if f["severity"] == "warning"]
    if not errors and not warns:
        return 0
    lines = [f"odoo-master validation for {rel} (Odoo {series or 'unknown'}):"]
    for f in (errors + warns)[:12]:
        lines.append(f"- {f['severity']} [{f['rule']}] line {f['line'] or '?'}: {f['message']}" + (f" Fix: {f['fix']}" if f.get("fix") else ""))
    out({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "\n".join(lines)}})
    return 0


def run() -> int:
    return safe_main(main)
