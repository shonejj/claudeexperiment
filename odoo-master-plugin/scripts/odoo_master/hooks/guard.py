"""PreToolUse guard: Bash commands (git / database / deployment / secrets) and Edit/Write targets.

Decisions: deny > ask > allow(=no output). "ask" becomes "deny" in non-interactive permission modes
(bypassPermissions, dontAsk) because nobody is there to answer — those actions need a recorded approval.
"""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path

from ..config import load_config, policy
from ..util import read_json, state_dir
from . import out, project_root, safe_main

NON_INTERACTIVE = {"bypassPermissions", "dontAsk"}
SECRET_READ = re.compile(r"(^|[\s;&|])(cat|less|more|head|tail|bat|type)\s+[^|;&]*?(\.env\b|\.pgpass|id_rsa|\.pem\b|\.key\b|odoo\.conf\b)")
ENV_DUMP = re.compile(r"(^|[\s;&|])(printenv|env)\s*($|[|;&])|echo\s+\$\{?(PGPASSWORD|[A-Z_]*(TOKEN|SECRET|PASSWORD|API_KEY))")
WRITE_SQL = re.compile(r"\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|ALTER\s+TABLE|DROP\s|TRUNCATE|CREATE\s+INDEX)\b", re.I)


def _decide(decision: str, reason: str, payload: dict) -> int:
    if decision == "ask" and payload.get("permission_mode") in NON_INTERACTIVE:
        decision, reason = "deny", reason + " (non-interactive session: needs a recorded human approval first)"
    out({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision,
                                "permissionDecisionReason": f"[odoo-master guard] {reason}"}})
    return 0


def check_bash(cmd: str, cfg: dict) -> tuple[str, str] | None:
    git = policy(cfg, "git-safety")
    for pat in git.get("deny", []):
        if re.search(pat, cmd):
            return "deny", f"git-safety: '{pat}' is never run automatically (force push / history rewrite)."
    dbp = policy(cfg, "database-safety")
    prod = [p for p in cfg.get("production_patterns", [])]
    targets = []
    for pat in dbp.get("always_production_check", []):
        targets += [m.group(1) for m in re.finditer(pat, cmd)]
    hits_prod = [t for t in targets if any(re.search(p, t, re.I) for p in prod)]
    if hits_prod and (WRITE_SQL.search(cmd) or re.search(r"\s-(u|i)\s|--update|--init|neutralize|db\s+(drop|load|rename)", cmd)):
        return "deny", f"database-safety: write/upgrade against production-looking database {hits_prod[0]!r}. Production changes need an approved migration plan and a human operator."
    for pat in dbp.get("blocked_without_approval", []):
        if re.search(pat, cmd, re.I):
            return "ask", f"database-safety: destructive or bulk database operation matched '{pat}'. Confirm the target is a disposable test database and a backup exists."
    for pat in policy(cfg, "deployment-safety").get("deny_without_approval", []):
        if re.search(pat, cmd, re.I):
            return "ask", f"deployment-safety: '{pat}' affects deployments or persistent volumes."
    for pat in git.get("ask", []):
        if re.search(pat, cmd):
            return "ask", f"git-safety: '{pat}' can discard work or change shared history."
    if SECRET_READ.search(cmd):
        return "ask", "security: this prints a credentials file. Use `odoo-master analyze` (redacts secrets) or read only the keys you need."
    if ENV_DUMP.search(cmd):
        return "ask", "security: this may print secrets from the environment."
    return None


def _match_any(path: str, patterns: list[str]) -> str | None:
    for p in patterns:
        if fnmatch.fnmatch(path, p) or fnmatch.fnmatch(path, "*/" + p):
            return p
    return None


def check_edit(file_path: str, content: str, root: Path, cfg: dict) -> tuple[str, str] | None:
    sec = policy(cfg, "security")
    try:
        rel = str(Path(file_path).resolve().relative_to(root))
    except ValueError:
        rel = file_path
    prot = sec.get("protected_paths", {})
    if _match_any(rel, prot.get("deny", [])):
        return "deny", f"security: {rel} is a protected path."
    inv = read_json(state_dir(root, create=False) / "project-inventory.json") or {}
    core_paths = (inv.get("odoo") or {}).get("protected_core_paths") or []
    if any(rel == c or rel.startswith(c.rstrip("/") + "/") for c in core_paths) or _match_any(rel, prot.get("ask", [])):
        return "ask", (f"Odoo core/Enterprise file {rel}: standard code must not be modified. "
                       "Use _inherit / view inheritance / patch() in a custom module instead. Approve only if this is intentional.")
    ver = read_json(state_dir(root, create=False) / "odoo-version.json") or {}
    if ver.get("conflicts") and Path(file_path).suffix in (".py", ".xml", ".csv", ".js"):
        fp = Path(file_path).resolve()
        if any((anc / "__manifest__.py").exists() for anc in fp.parents if str(anc).startswith(str(root))):
            kinds = ", ".join(sorted({c.get("type", "?") for c in ver["conflicts"]}))
            from ..util import PLUGIN_ROOT
            return "ask", (f"Odoo version signals conflict ({kinds}); detected {ver.get('version')}. If the user already named the target series, "
                           f"record it with `{PLUGIN_ROOT}/bin/odoo-master detect-version --confirm <series>`; otherwise ask the user first. "
                           "Module code edits are held until the series is confirmed.")
    for pat in sec.get("secrets", {}).get("block_commit_patterns", []):
        if content and re.search(pat, content):
            if rel.endswith((".example", ".sample", ".md")) and "REDACTED" in content:
                continue
            return "ask", f"security: content looks like a hard-coded secret (pattern {pat!r}). Use environment variables or Odoo system parameters."
    return None


def main(payload: dict) -> int:
    tool = payload.get("tool_name", "")
    ti = payload.get("tool_input") or {}
    root = project_root(payload)
    cfg = load_config(root)
    res = None
    if tool == "Bash":
        res = check_bash(ti.get("command", ""), cfg)
    elif tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        content = ti.get("content") or ti.get("new_string") or "\n".join(e.get("new_string", "") for e in ti.get("edits", []) or [])
        res = check_edit(ti.get("file_path") or ti.get("notebook_path") or "", content, root, cfg)
    if res:
        return _decide(res[0], res[1], payload)
    if tool in ("Edit", "Write", "MultiEdit") and ti.get("file_path"):
        from .post_edit import snapshot_baseline
        try:
            snapshot_baseline(payload, ti["file_path"])   # pre-existing findings, so the Stop gate only blocks on new ones
        except Exception:  # noqa: BLE001 - never block an edit because the snapshot failed
            pass
    return 0


def run() -> int:
    return safe_main(main)
