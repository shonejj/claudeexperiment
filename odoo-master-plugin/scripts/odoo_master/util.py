"""Shared helpers: paths, JSON/YAML IO, redaction, project root discovery, state dir."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parents[2])
STATE_DIR_NAME = ".odoo-master"

try:  # PyYAML is optional for hooks; required for workflows/policies editing.
    import yaml  # type: ignore
except Exception:  # pragma: no cover - exercised when PyYAML is missing
    yaml = None


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def load_yaml(path: Path | str) -> Any:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text)
    # Minimal fallback: JSON is valid YAML. Plugin YAML files ship a .json twin when needed.
    twin = path.with_suffix(".json")
    if twin.exists():
        return json.loads(twin.read_text(encoding="utf-8"))
    raise RuntimeError(f"PyYAML is not installed and no JSON twin exists for {path}")


def dump_yaml(data: Any) -> str:
    if yaml is None:
        return json.dumps(data, indent=2)
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def read_json(path: Path | str, default: Any = None) -> Any:
    path = Path(path)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def write_json(path: Path | str, data: Any) -> Path:
    """Atomic JSON write (write temp + rename) so a crash never leaves half a checkpoint."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=False, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def append_jsonl(path: Path | str, record: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def find_project_root(start: Path | str | None = None) -> Path:
    """CLAUDE_PROJECT_DIR wins; otherwise nearest parent with .git; otherwise start."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env and Path(env).is_dir():
        return Path(env).resolve()
    cur = Path(start or os.getcwd()).resolve()
    for p in [cur, *cur.parents]:
        if (p / ".git").exists():
            return p
    return cur


def state_dir(project_root: Path | str | None = None, create: bool = True) -> Path:
    root = Path(project_root) if project_root else find_project_root()
    d = root / STATE_DIR_NAME
    if create:
        d.mkdir(parents=True, exist_ok=True)
        gi = d / ".gitignore"
        if not gi.exists():
            # Wudo-free, tool-owned file. Plans/reports/evidence are kept (reviewable);
            # volatile runtime state is ignored.
            gi.write_text("logs/\nsession/\ncache/\nexecutions/*.lock\n*.tmp\n", encoding="utf-8")
    return d


# ---------------------------------------------------------------- redaction
_SECRET_KEY_RE = re.compile(r"(pass(word)?|passwd|secret|token|api[_-]?key|auth|credential|private[_-]?key|session)", re.I)
_SECRET_VALUE_RES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "***REDACTED***"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "***REDACTED***"),
    (re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}"), "***REDACTED***"),
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "***REDACTED***"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "***REDACTED***"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "***REDACTED***"),
    (re.compile(r"(?P<pre>postgres(?:ql)?://[^:\s/@]+:)[^@\s]+(?P<at>@)"), r"\g<pre>***REDACTED***\g<at>"),
    (re.compile(r"(?i)(?P<k>\b(?:admin_passwd|db_password|password|passwd|secret|token|api_key|PGPASSWORD)\b)(?P<sep>\s*[=:]\s*)(?P<v>[^\s,;]+)"),
     r"\g<k>\g<sep>***REDACTED***"),
]
REDACTED = "***REDACTED***"


def redact_text(text: str) -> str:
    if not text:
        return text
    out = text
    for rx, repl in _SECRET_VALUE_RES:
        out = rx.sub(repl, out)
    return out


def redact(obj: Any) -> Any:
    """Recursively redact secret-looking keys and values."""
    if isinstance(obj, dict):
        res = {}
        for k, v in obj.items():
            if isinstance(k, str) and _SECRET_KEY_RE.search(k) and isinstance(v, (str, int, float)) and str(v) not in ("", "False", "None"):
                res[k] = REDACTED
            else:
                res[k] = redact(v)
        return res
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    if isinstance(obj, str):
        return redact_text(obj)
    return obj


# ---------------------------------------------------------------- subprocess
def run(cmd: list[str] | str, cwd: Path | str | None = None, timeout: int = 120, env: dict | None = None,
        shell: bool = False) -> dict:
    """Run a command and return a JSON-able record (stdout/stderr redacted, truncated)."""
    started = now_iso()
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                              env={**os.environ, **(env or {})}, shell=shell)
        rc, out, err = proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError as exc:
        rc, out, err = 127, "", str(exc)
    except subprocess.TimeoutExpired as exc:
        rc, out, err = 124, (exc.stdout or "") if isinstance(exc.stdout, str) else "", f"timeout after {timeout}s"
    return {
        "command": cmd if isinstance(cmd, str) else " ".join(cmd),
        "cwd": str(cwd) if cwd else None,
        "exit_code": rc,
        "started_at": started,
        "finished_at": now_iso(),
        "stdout": redact_text(out)[-20000:],
        "stderr": redact_text(err)[-8000:],
    }


def iter_files(root: Path, patterns: Iterable[str] | None = None, skip_dirs: Iterable[str] = ()) -> Iterable[Path]:
    skip = {".git", "node_modules", "__pycache__", ".venv", "venv", STATE_DIR_NAME, *skip_dirs}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".tox")]
        for fn in filenames:
            p = Path(dirpath) / fn
            if patterns is None or any(p.match(pat) for pat in patterns):
                yield p


def emit(data: Any, as_json: bool = True) -> None:
    if as_json:
        sys.stdout.write(json.dumps(data, indent=2, default=str) + "\n")
    else:
        sys.stdout.write(str(data) + "\n")


def version_tuple(v: str | None) -> tuple:
    if not v:
        return (0,)
    nums = re.findall(r"\d+", str(v))
    return tuple(int(n) for n in nums[:2]) or (0,)
