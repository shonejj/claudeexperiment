"""Migration scanning and planning between Odoo series.

`scan()` applies every knowledge rule whose `since` lies in (source, target] to the given modules and
returns blockers (errors), required changes (warnings) and a step-by-step hop plan (one major at a time).
`plan_skeleton()` produces the structured migration plan consumed by templates/migration-plans.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import knowledge, known_series
from .inventory import find_modules, classify_module_location, parse_manifest
from ..util import iter_files, version_tuple, now_iso


def hops(source: str, target: str) -> list[str]:
    s, t = version_tuple(source), version_tuple(target)
    return [v for v in known_series() if s < version_tuple(v) <= t]


def scan(root: Path | str, source: str, target: str, modules: list[str] | None = None) -> dict:
    root = Path(root).resolve()
    s, t = version_tuple(source), version_tuple(target)
    if t <= s:
        raise ValueError(f"target {target} must be newer than source {source}")
    rules = [r for r in knowledge()["rules"] if r.get("check", True) and r["severity"] != "info"
             and s < version_tuple(r["since"]) <= t]
    mods = [m for m in find_modules(root) if classify_module_location(m, root) == "custom"]
    if modules:
        mods = [m for m in mods if m.name in modules]
    per_module = {}
    for mod in mods:
        items = []
        for p in iter_files(mod):
            if p.suffix not in (".py", ".xml", ".js", ".csv") or "migrations" in p.parts or "upgrades" in p.parts:
                continue
            text = None
            for r in rules:
                if not any(p.match(g) for g in r["files"]):
                    continue
                text = text if text is not None else p.read_text(encoding="utf-8", errors="ignore")
                for m in re.finditer(r["pattern"], text, re.M):
                    items.append({"rule": r["id"], "since": r["since"], "severity": r["severity"],
                                  "file": str(p.relative_to(root)), "line": text.count("\n", 0, m.start()) + 1,
                                  "message": r["message"], "source": r.get("doc")})
                    if r["pattern"] == ".":
                        break
        manifest, _ = parse_manifest(mod / "__manifest__.py")
        stored_fields = []
        per_module[mod.name] = {
            "path": str(mod.relative_to(root)),
            "current_version": (manifest or {}).get("version"),
            "suggested_version": f"{target}.1.0.0" if manifest else None,
            "depends": (manifest or {}).get("depends") or [],
            "findings": items,
            "blockers": sum(1 for i in items if i["severity"] == "error"),
            "changes": sum(1 for i in items if i["severity"] == "warning"),
            "has_migration_scripts": (mod / "migrations").is_dir() or (mod / "upgrades").is_dir(),
            "stored_fields": stored_fields,
        }
    return {"generated_at": now_iso(), "source": source, "target": target, "hops": hops(source, target),
            "rules_applied": [r["id"] for r in rules], "modules": per_module,
            "totals": {"blockers": sum(m["blockers"] for m in per_module.values()),
                       "changes": sum(m["changes"] for m in per_module.values())},
            "automated_tooling": {
                "upgrade_code": f"odoo-bin upgrade_code --addons-path <custom_addons> --from {source} --to {target} --dry-run"
                if version_tuple(target) >= (18,) else None,
                "note": "upgrade_code exists in Odoo 18.0+ sources; run it with the TARGET version's odoo-bin, review every rewritten file.",
            }}


def plan_skeleton(scan_result: dict, risk_notes: list[str] | None = None) -> dict:
    steps = []
    for hop in scan_result["hops"]:
        steps.append({"hop": hop, "actions": [
            f"Create branch migrate/{hop}",
            f"Run odoo-bin upgrade_code --from <previous> --to {hop} --dry-run (if available) and review",
            "Apply rule findings for this hop (see findings with since == hop)",
            "Bump manifest versions to {hop}.x.y.z and add migrations/<version>/pre-|post- scripts for renamed/removed stored fields",
            f"Install test on a fresh {hop} database with --test-tags /<module>",
            "Upgrade test on a neutralized, already-upgraded copy of production data",
        ]})
    return {
        "source": scan_result["source"], "target": scan_result["target"], "hops": scan_result["hops"],
        "modules": {n: {"blockers": m["blockers"], "changes": m["changes"]} for n, m in scan_result["modules"].items()},
        "steps": steps,
        "validation": [
            "0 blocker findings for the target version (migration scan)",
            "module installs on target with tests passing (runtime level)",
            "module upgrades on a copy of real data; row counts of affected tables unchanged; spot checks pass",
            "server log summary has 0 ERROR/CRITICAL lines and 0 tracebacks",
        ],
        "rollback": ["Restore the pre-upgrade pg_dump and filestore copy (paths + sha256 recorded in evidence)",
                     "Redeploy the previous git tag / image tag"],
        "risks": risk_notes or [],
        "requires_approval": ["production upgrade", "any data transformation on production", "schema changes with data loss"],
    }
