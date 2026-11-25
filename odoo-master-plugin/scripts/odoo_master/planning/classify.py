"""Deterministic request signals for classification.

This is deliberately *not* the classifier: the orchestrator (an LLM) decides the intent. This module
supplies facts the model should not guess — which existing modules/models/apps the request
mentions, ticket/PR/thread references, versions mentioned, and keyword-based intent candidates with
scores — so the decision is grounded and auditable.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..config import load_config
from ..util import read_json, state_dir

INTENT_KEYWORDS = {
    "migration": [r"\bmigrat", r"\bupgrad", r"\bport(ing)?\b", r"\bfrom (odoo )?1\d(\.0)? to (odoo )?[12]\d"],
    "bug_fix": [r"\bbug\b", r"\bfix", r"\berror\b", r"traceback", r"\bbroken\b", r"\bfails?\b", r"\bcrash", r"\bexception\b", r"doesn'?t work"],
    "new_module": [r"\bnew (custom )?module\b", r"\bcreate (a |an )?(custom )?module\b", r"\bbuild (a |an )?(new )?(custom )?(odoo )?(module|app)\b"],
    "module_enhancement": [r"\badd (a |new )?(custom )?fields?\b", r"\bcustomi[sz]e\b", r"\bextend\b", r"\benhanc", r"\bimprove\b", r"\bform view\b"],
    "database_investigation": [r"\bdatabase\b", r"\bpostgres", r"\bsql\b", r"\bconstraint\b", r"\bdata (issue|inconsisten|corrupt)"],
    "performance": [r"\bslow\b", r"\bperformance\b", r"\btimeout", r"\bn\+1\b", r"\bspeed\b", r"\boptimi[sz]"],
    "security_audit": [r"\bsecurity (audit|review)\b", r"\baccess rights?\b", r"\bpermissions? audit\b", r"\bvulnerab"],
    "deployment": [r"\bdeploy", r"\bstaging\b", r"\bproduction rollout\b", r"\brelease\b"],
    "pull_request_review": [r"\breview (the |this )?(pr|pull request)\b", r"/pull/\d+"],
    "code_review": [r"\bcode review\b", r"\breview (my|the) (changes|diff|code)\b"],
    "ticket_planning": [r"\bplan\b.*\bticket\b", r"\bticket\b.*\b(plan|estimate|analy[sz]e)"],
    "ticket_implementation": [r"\bimplement\b.*\b[A-Z][A-Z0-9]+-\d+\b", r"\bimplement (the )?ticket\b"],
    "github_issue": [r"github\.com/[^/]+/[^/]+/issues/\d+"],
    "slack_report": [r"slack\.com/archives/"],
    "integration": [r"\bintegrat", r"\bapi\b", r"\bwebhook", r"\bconnector\b", r"\bsync\b"],
    "report": [r"\breport\b", r"\bpdf\b", r"\bqweb\b"],
    "owl_frontend": [r"\bowl\b", r"\bwidget\b", r"\bjavascript\b", r"\bjs\b", r"\bclient action\b"],
}
APP_KEYWORDS = {
    "accounting": ["account", "invoice", "bill", "journal", "payment", "tax", "accounting"],
    "inventory": ["stock", "inventory", "picking", "warehouse", "receipt", "delivery", "lot", "serial"],
    "sales": ["sale", "quotation", "sales order", "pricelist", "crm"],
    "purchase": ["purchase", "rfq", "vendor", "supplier"],
    "manufacturing": ["mrp", "manufactur", "bom", "work order", "production"],
    "hr": ["hr", "employee", "leave", "payroll", "attendance", "timesheet", "expense"],
    "website": ["website", "ecommerce", "e-commerce", "portal", "web page"],
    "pos": ["pos", "point of sale"],
    "project": ["project", "task"],
}
RISK_WORDS = {"critical": [r"\bproduction\b.*\b(data|database|migrat)", r"\bdelete\b.*\bdata\b"],
              "high": [r"\baccounting\b", r"\bmigrat", r"\bproduction\b", r"\bpayroll\b", r"\binvoice"]}


def classify(request: str, root: Path | None = None) -> dict:
    text = request or ""
    low = text.lower()
    scores = {}
    for intent, pats in INTENT_KEYWORDS.items():
        s = sum(1 for p in pats if re.search(p, text, re.I))
        if s:
            scores[intent] = s
    inv = read_json(state_dir(root, create=False) / "project-inventory.json") or {}
    modules = list((inv.get("modules") or {}).keys())
    mentioned_modules = [m for m in modules if re.search(rf"\b{re.escape(m)}\b", text)]
    models = set()
    for m in (inv.get("modules") or {}).values():
        for mdl in m.get("models", []):
            if mdl.get("name"):
                models.add(mdl["name"])
    mentioned_models = sorted({m for m in models if m in text} | set(re.findall(r"\b[a-z_]+\.[a-z_]+(?:\.[a-z_]+)?\b", text)) & models)
    apps = sorted(a for a, kws in APP_KEYWORDS.items() if any(k in low for k in kws))
    versions = sorted(set(re.findall(r"\b(1[4-9]|2[0-9])(?:\.0)?\b", text)) - set(), key=int)
    refs = {"tickets": sorted(set(re.findall(r"\b[A-Z][A-Z0-9]{1,9}-\d{1,6}\b", text))),
            "github": re.findall(r"github\.com/[\w.-]+/[\w.-]+/(?:issues|pull)/\d+", text),
            "slack": re.findall(r"https://[\w-]+\.slack\.com/archives/\S+", text)}
    if mentioned_modules and "new_module" in scores and "module_enhancement" not in scores:
        scores["module_enhancement"] = 1  # names an existing module: may not need a new one
    risk = "medium"
    for lvl in ("critical", "high"):
        if any(re.search(p, low) for p in RISK_WORDS[lvl]):
            risk = lvl
            break
    if not scores and not modules:
        scores["general_software"] = 1
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    cfg = load_config(root)
    wmap = (cfg.get("workflows") or {}).get("default_for_intent") or {}
    candidates = [{"intent": k, "score": v, "workflow": wmap.get(k)} for k, v in ranked]
    ambiguous = len(ranked) > 1 and ranked[0][1] == ranked[1][1]
    return {
        "request": text,
        "candidates": candidates,
        "ambiguous": ambiguous,
        "odoo_project": bool(modules) or bool((inv.get("odoo") or {}).get("version")),
        "odoo_version": (inv.get("odoo") or {}).get("version"),
        "versions_mentioned": [f"{v}.0" for v in versions],
        "existing_modules_mentioned": mentioned_modules,
        "models_mentioned": mentioned_models,
        "apps": apps,
        "references": refs,
        "risk_hint": risk,
        "note": "Signals only. Decide the intent with judgement; ask the user when ambiguous or when the target module is unclear.",
    }
