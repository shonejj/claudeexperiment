"""Read-only access to standard Odoo source inside the official Docker images (no clone needed).

  grep(pattern, series, module=None)   -> matches with path:line (standard addons of that series)
  show(path, series, start, end)       -> a slice of a standard file (e.g. a base view to find XPath anchors)
  lookup_model(model, series)          -> defining module + extending modules (offline knowledge maps)
  lookup_module(module, series)        -> depends + transitive closure + models defined (offline)
  upgrade_code(addons, src, dst, ...)  -> run `odoo upgrade_code` of the target image over custom addons
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from . import dependency_closure, standard_models, standard_modules

ODOO_PKG = "/usr/lib/python3/dist-packages/odoo"
_SAFE_REL = re.compile(r"^[\w./-]+$")


def _image(series: str, image: str | None) -> str:
    return image or f"odoo:{series}"


def _need_docker():
    if not shutil.which("docker"):
        raise RuntimeError("docker CLI not installed")


def grep(pattern: str, series: str, module: str | None = None, image: str | None = None, max_results: int = 200,
         include: str = "*.py,*.xml,*.js,*.csv") -> dict:
    _need_docker()
    if module and not re.match(r"^[a-z0-9_]+$", module):
        raise ValueError("invalid module name")
    base = f"{ODOO_PKG}/addons/{module}" if module else f"{ODOO_PKG}/addons"
    incl = [f"--include={g.strip()}" for g in include.split(",") if g.strip()]
    r = subprocess.run(["docker", "run", "--rm", "--entrypoint", "grep", _image(series, image), "-rnE", *incl, "--", pattern, base],
                       capture_output=True, text=True, timeout=300)
    if r.returncode not in (0, 1):
        raise RuntimeError(r.stderr.strip()[:400])
    matches = []
    for ln in r.stdout.splitlines()[:max_results]:
        m = re.match(r"^(.+?):(\d+):(.*)$", ln)
        if m:
            matches.append({"path": m.group(1).replace(f"{ODOO_PKG}/", "odoo/"), "line": int(m.group(2)), "text": m.group(3)[:300]})
    return {"series": series, "pattern": pattern, "module": module, "count": len(matches),
            "truncated": len(r.stdout.splitlines()) > max_results, "matches": matches}


def show(path: str, series: str, start: int = 1, end: int | None = None, image: str | None = None) -> dict:
    _need_docker()
    rel = path.removeprefix("odoo/")
    if not _SAFE_REL.match(rel) or ".." in rel:
        raise ValueError("path must be relative to the odoo package, e.g. addons/stock/views/stock_picking_views.xml")
    end = end or start + 200
    r = subprocess.run(["docker", "run", "--rm", "--entrypoint", "sed", _image(series, image), "-n", f"{int(start)},{int(end)}p",
                        f"{ODOO_PKG}/{rel}"], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:400] or f"cannot read {rel}")
    lines = r.stdout.splitlines()
    return {"series": series, "path": f"odoo/{rel}", "start": start, "end": start + len(lines) - 1,
            "content": "\n".join(f"{i:>5}  {t}" for i, t in enumerate(lines, start))}


def lookup_model(model: str, series: str) -> dict:
    m = standard_models(series)
    return {"model": model, "series": series, "defined_in": m["defined_in"].get(model),
            "extended_in": m["extended_in"].get(model, []), "known": model in m["defined_in"],
            "note": None if model in m["defined_in"] else "Not a Community model of this series (Enterprise, third-party, or a typo)."}


def lookup_module(module: str, series: str) -> dict:
    graph = standard_modules(series)
    if module not in graph:
        return {"module": module, "series": series, "known": False}
    defined = sorted(k for k, v in standard_models(series)["defined_in"].items() if v == module)
    closure = sorted(dependency_closure(graph[module], series))
    dependents = sorted(k for k, deps in graph.items() if module in deps)
    return {"module": module, "series": series, "known": True, "depends": graph[module], "depends_closure": closure,
            "direct_dependents": dependents[:80], "models_defined": defined}


def upgrade_code(addons: str, source: str, target: str, dry_run: bool = True, image: str | None = None, script: str | None = None) -> dict:
    """Run the target image's `odoo upgrade_code` over a custom addons directory (18.0+ images).
    Without dry_run the directory is mounted read-write and files are rewritten in place."""
    _need_docker()
    path = Path(addons).resolve()
    if not path.is_dir():
        raise FileNotFoundError(addons)
    mode = "ro" if dry_run else "rw"
    # bypass the image entrypoint: it waits for a database, which upgrade_code does not need
    args = ["upgrade_code", "--addons-path", "/mnt/upgrade"]
    args += ["--script", script] if script else ["--from", source, "--to", target]
    if dry_run:
        args.append("--dry-run")
    # run as the host user so rewritten files keep their ownership
    import os
    user = ["--user", f"{os.getuid()}:{os.getgid()}"] if hasattr(os, "getuid") else []
    r = subprocess.run(["docker", "run", "--rm", *user, "--entrypoint", "/usr/bin/odoo", "-v", f"{path}:/mnt/upgrade:{mode}",
                        _image(target, image), *args],
                       capture_output=True, text=True, timeout=1800)
    out = (r.stdout + r.stderr).strip()
    files = sorted({m.group(1) for m in re.finditer(r"(/mnt/upgrade/[^\s:]+)", out)})
    return {"source": source, "target": target, "dry_run": dry_run, "exit_code": r.returncode,
            "files": [f.replace("/mnt/upgrade/", "") for f in files], "output_tail": out[-4000:]}
