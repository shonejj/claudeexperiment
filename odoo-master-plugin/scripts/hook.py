#!/usr/bin/env python3
"""Entry point for all Odoo Master hooks: `hook.py <name>` (see hooks/hooks.json)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

HOOKS = {
    "session-start": ("odoo_master.hooks.session_start", "run"),
    "guard": ("odoo_master.hooks.guard", "run"),
    "post-edit": ("odoo_master.hooks.post_edit", "run"),
    "stop-gate": ("odoo_master.hooks.stop_gate", "run"),
    "pre-compact": ("odoo_master.hooks.misc", "run_precompact"),
    "prompt": ("odoo_master.hooks.misc", "run_prompt"),
    "mcp-post": ("odoo_master.hooks.misc", "run_mcp_post"),
    "mcp-failure": ("odoo_master.hooks.misc", "run_mcp_failure"),
}

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if name not in HOOKS:
        print(f"unknown hook {name!r}", file=sys.stderr)
        sys.exit(0)
    mod, fn = HOOKS[name]
    import importlib
    sys.exit(getattr(importlib.import_module(mod), fn)())
