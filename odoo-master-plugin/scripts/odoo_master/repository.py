"""Repository facts: git state, remotes, branches, environment files (Docker, Python, configs).

Never prints secrets: odoo.conf values for password-like keys are redacted, .env files are only
listed by name (their keys, not values).
"""
from __future__ import annotations

import configparser
import re
import shutil
from pathlib import Path

from .util import iter_files, redact, run


def git(root: Path, *args: str) -> str:
    r = run(["git", *args], cwd=root, timeout=30)
    return r["stdout"].strip() if r["exit_code"] == 0 else ""


def git_state(root: Path) -> dict:
    if not shutil.which("git") or not (root / ".git").exists() and not git(root, "rev-parse", "--git-dir"):
        return {"is_git": False}
    status = git(root, "status", "--porcelain=v1")
    remotes = {}
    for line in git(root, "remote", "-v").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            remotes[parts[0]] = re.sub(r"//[^@/]+@", "//", parts[1])  # strip embedded credentials
    default = git(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").replace("origin/", "") or None
    gh = None
    url = remotes.get("origin", "")
    m = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", url)
    if m:
        gh = {"owner": m.group(1), "repo": m.group(2)}
    return {
        "is_git": True,
        "branch": git(root, "rev-parse", "--abbrev-ref", "HEAD") or None,
        "head": git(root, "rev-parse", "--short", "HEAD") or None,
        "default_branch": default,
        "remotes": remotes,
        "github": gh,
        "branches": git(root, "branch", "--format=%(refname:short)").splitlines()[:50],
        "dirty": bool(status),
        "changed_files": [ln[3:] for ln in status.splitlines() if ln and not ln.startswith("??")][:200],
        "untracked_files": [ln[3:] for ln in status.splitlines() if ln.startswith("??")][:200],
        "recent_commits": git(root, "log", "--oneline", "-15").splitlines(),
    }


def environment(root: Path) -> dict:
    env = {"docker": [], "compose": [], "odoo_conf": [], "requirements": [], "python": {}, "env_files": [],
           "odoo_sh": False, "ci": []}
    for p in iter_files(root):
        rel = str(p.relative_to(root))
        n = p.name
        if n.startswith("Dockerfile"):
            env["docker"].append(rel)
        elif n in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
            env["compose"].append(rel)
        elif n.endswith(".conf") and "odoo" in n.lower() or n == "odoo.conf":
            env["odoo_conf"].append(parse_odoo_conf(p, rel))
        elif n == "requirements.txt":
            env["requirements"].append(rel)
        elif n == ".env" or n.endswith(".env"):
            keys = [ln.split("=", 1)[0].strip() for ln in p.read_text(errors="ignore").splitlines() if "=" in ln and not ln.startswith("#")]
            env["env_files"].append({"file": rel, "keys": keys})
        elif rel.startswith(".github/workflows/") or n in (".gitlab-ci.yml", "Jenkinsfile", ".travis.yml"):
            env["ci"].append(rel)
        elif n in (".odoo.sh", "odoo_sh.yml") or rel.startswith(".odoo_sh"):
            env["odoo_sh"] = True
    for n in ("pyproject.toml", ".python-version", "setup.cfg", "Pipfile"):
        if (root / n).exists():
            env["python"][n] = True
    return env


def parse_odoo_conf(path: Path, rel: str) -> dict:
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        cp.read_string(path.read_text(errors="ignore"))
    except configparser.Error as exc:
        return {"file": rel, "error": str(exc)}
    opts = dict(cp.items("options")) if cp.has_section("options") else {}
    keep = {k: v for k, v in opts.items() if k in ("addons_path", "db_host", "db_port", "db_name", "dbfilter", "workers",
                                                       "proxy_mode", "list_db", "data_dir", "gevent_port", "longpolling_port",
                                                       "max_cron_threads", "limit_time_real", "limit_memory_hard", "db_user",
                                                       "admin_passwd", "db_password", "server_wide_modules")}
    return {"file": rel, "options": redact(keep)}
