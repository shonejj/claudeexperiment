"""Effort estimation from a task breakdown (schemas/estimate.schema.json).

hours(task) = base[complexity] * Π multipliers (new_module, touches_standard_flow, data_migration)
              * (1 + per_unknown * unknowns)
total = Σ hours * (1 + testing + review + documentation overhead)
range = total * (1 ± spread[confidence])     spread: high 0.15, medium 0.3, low 0.5
These are effort estimates, not delivery commitments.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..config import load_config
from ..schemas import validate_data

SPREAD = {"high": 0.15, "medium": 0.30, "low": 0.50}
AGENT_FOR_KIND = {"model": "odoo-python-specialist", "view": "odoo-frontend-specialist", "security": "odoo-security-specialist",
                  "controller": "odoo-python-specialist", "owl": "odoo-owl-specialist", "report": "odoo-frontend-specialist",
                  "data": "odoo-developer", "migration": "odoo-migration-specialist", "integration": "integration-engineer",
                  "test": "test-automation-engineer", "devops": "devops-engineer", "analysis": "odoo-architect",
                  "docs": "documentation-writer", "review": "code-reviewer"}


def estimate(data: dict, root: Path | None = None) -> dict:
    v = validate_data("estimate", data)
    if not v["valid"]:
        raise ValueError(f"invalid estimate input: {v['errors']}")
    cfg = (load_config(root).get("estimation") or {})
    base = cfg.get("hours_per_complexity") or {"trivial": 0.5, "simple": 2, "moderate": 6, "complex": 16, "very_complex": 32}
    mult = cfg.get("multipliers") or {}
    over = cfg.get("overhead") or {"testing": 0.3, "review": 0.1, "documentation": 0.05}
    hpd = float(cfg.get("hours_per_day", 6))
    rows, by_agent = [], defaultdict(float)
    for t in data["tasks"]:
        h = float(base[t["complexity"]])
        factors = []
        for flag in ("new_module", "touches_standard_flow", "data_migration"):
            if t.get(flag):
                h *= float(mult.get(flag, 1))
                factors.append(flag)
        if t.get("unknowns"):
            h *= 1 + float(mult.get("per_unknown", 0.15)) * int(t["unknowns"])
            factors.append(f"{t['unknowns']} unknown(s)")
        rows.append({"id": t["id"], "title": t["title"], "module": t.get("module"), "kind": t["kind"], "complexity": t["complexity"],
                     "hours": round(h, 1), "factors": factors})
        by_agent[AGENT_FOR_KIND.get(t["kind"], "odoo-developer")] += h
    impl = sum(r["hours"] for r in rows)
    overhead = {k: round(impl * float(v), 1) for k, v in over.items()}
    total = impl + sum(overhead.values())
    by_agent["qa-engineer"] += overhead.get("testing", 0)
    by_agent["code-reviewer"] += overhead.get("review", 0)
    by_agent["documentation-writer"] += overhead.get("documentation", 0)
    conf = data.get("confidence", "medium")
    s = SPREAD.get(conf, 0.3)
    complexity_level = "low" if total < 8 else "medium" if total < 40 else "high" if total < 120 else "very high"
    return {"title": data.get("title"), "ticket": data.get("ticket"), "confidence": conf, "tasks": rows,
            "implementation_hours": round(impl, 1), "overhead_hours": overhead, "total_hours": round(total, 1),
            "range_hours": [round(total * (1 - s), 1), round(total * (1 + s), 1)],
            "development_days": round(total / hpd, 1), "range_days": [round(total * (1 - s) / hpd, 1), round(total * (1 + s) / hpd, 1)],
            "complexity_level": complexity_level,
            "agent_workload_hours": {k: round(v, 1) for k, v in sorted(by_agent.items(), key=lambda kv: -kv[1])},
            "testing_effort_hours": overhead.get("testing"),
            "disclaimer": "Effort estimate based on repository analysis and stated assumptions; not a delivery commitment."}


def to_markdown(est: dict) -> str:
    lines = [f"## Estimate{': ' + est['title'] if est.get('title') else ''}", "",
             "| # | Task | Module | Kind | Complexity | Hours | Factors |", "|---|---|---|---|---|---|---|"]
    for t in est["tasks"]:
        lines.append(f"| {t['id']} | {t['title']} | {t.get('module') or ''} | {t['kind']} | {t['complexity']} | {t['hours']} | {', '.join(t['factors'])} |")
    lines += ["", f"- Implementation: **{est['implementation_hours']} h**; overhead: " + ", ".join(f"{k} {v} h" for k, v in est["overhead_hours"].items()),
              f"- Total: **{est['total_hours']} h** (range {est['range_hours'][0]}–{est['range_hours'][1]} h), about **{est['development_days']} dev-days** "
              f"(range {est['range_days'][0]}–{est['range_days'][1]}), confidence {est['confidence']}, complexity {est['complexity_level']}.",
              f"- {est['disclaimer']}"]
    return "\n".join(lines) + "\n"
