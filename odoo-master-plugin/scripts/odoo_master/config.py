"""Configuration hierarchy.

Precedence (later wins):
  1. plugin defaults           <plugin>/config/defaults.yaml
  2. plugin policies           <plugin>/policies/*.yaml   (exposed under config["policies"][name])
  3. organisation file         $ODOO_MASTER_ORG_CONFIG (path to YAML), if set
  4. project file              <project>/.odoo-master/config.yaml
  5. plugin userConfig         CLAUDE_PLUGIN_OPTION_<KEY> environment variables
  6. explicit environment      ODOO_MASTER_<KEY> environment variables (top-level scalars)

Organisation-level *enforcement* is not done here: managed Claude Code settings and
infrastructure are the security boundary. This module only shapes agent behaviour.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

from .util import PLUGIN_ROOT, find_project_root, load_yaml, STATE_DIR_NAME

POLICY_NAMES = ["security", "approvals", "database-safety", "git-safety", "deployment-safety", "testing", "evidence"]


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _safe_yaml(path: Path) -> dict:
    try:
        data = load_yaml(path)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_config(project_root: Path | str | None = None) -> dict:
    root = Path(project_root) if project_root else find_project_root()
    cfg = _safe_yaml(PLUGIN_ROOT / "config" / "defaults.yaml")
    policies = {}
    for name in POLICY_NAMES:
        p = PLUGIN_ROOT / "policies" / f"{name}.yaml"
        if p.exists():
            policies[name] = _safe_yaml(p)
    cfg["policies"] = deep_merge(policies, cfg.get("policies", {}))
    org = os.environ.get("ODOO_MASTER_ORG_CONFIG")
    if org and Path(org).is_file():
        cfg = deep_merge(cfg, _safe_yaml(Path(org)))
    proj = root / STATE_DIR_NAME / "config.yaml"
    if proj.is_file():
        cfg = deep_merge(cfg, _safe_yaml(proj))
    # userConfig from plugin settings
    uc = {
        "autonomy": os.environ.get("CLAUDE_PLUGIN_OPTION_AUTONOMY"),
        "production_patterns": os.environ.get("CLAUDE_PLUGIN_OPTION_PRODUCTION_PATTERNS"),
        "default_odoo_version": os.environ.get("CLAUDE_PLUGIN_OPTION_DEFAULT_ODOO_VERSION"),
    }
    for k, v in uc.items():
        if v not in (None, ""):
            cfg[k] = v
    for k in ("autonomy", "production_patterns", "default_odoo_version"):
        v = os.environ.get(f"ODOO_MASTER_{k.upper()}")
        if v not in (None, ""):
            cfg[k] = v
    if isinstance(cfg.get("production_patterns"), str):
        cfg["production_patterns"] = [p.strip() for p in cfg["production_patterns"].split(",") if p.strip()]
    cfg.setdefault("autonomy", "checkpoint")
    cfg.setdefault("production_patterns", ["prod", "production", "live"])
    cfg["_project_root"] = str(root)
    return cfg


def policy(cfg: dict, name: str) -> dict:
    return (cfg.get("policies") or {}).get(name, {}) or {}


def get(cfg: dict, dotted: str, default: Any = None) -> Any:
    cur: Any = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur
