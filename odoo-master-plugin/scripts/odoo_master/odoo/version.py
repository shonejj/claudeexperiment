"""Odoo version detection from multiple independent signals.

Signals and weights (strong signals decide; weak ones only break ties):
  release_py      100  odoo/release.py version_info in or near the project
  docker          80   FROM odoo:<v> / image: odoo:<v> in Dockerfile / compose
  config          60   requirements pins (odoo==17.0...), .odoo-version, odoo.sh branch name hints
  manifest        40   per-manifest version prefix "<major>.0.x.y.z" (majority vote)
  fingerprint     15   syntax rules from knowledge/odoo-versions.yaml (bounds, not points)

The verdict lists every signal with its evidence (file:line) so the agent can cite it, and
`conflicts` whenever two strong signals disagree. Agents must stop and ask on conflicts.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from . import knowledge, known_series
from ..util import iter_files, version_tuple

_RELEASE_RE = re.compile(r"^version_info\s*=\s*\(\s*(?:['\"]?saas~)?(\d+)\s*,\s*(\d+)", re.M)
_DOCKER_RE = re.compile(r"(?:FROM|image:)\s*['\"]?(?:docker\.io/)?(?:library/)?odoo:(\d+)(?:\.(\d+))?", re.I)
_REQ_RE = re.compile(r"^\s*odoo\s*(?:==|~=|>=)\s*(\d+)\.(\d+)", re.I | re.M)
_MANIFEST_VER_RE = re.compile(r"['\"]version['\"]\s*:\s*['\"](\d+)\.(\d+)\.\d+", re.M)


def _series(major: int, minor: int = 0) -> str:
    return f"{major}.{minor}"


def _rel(root: Path, p: Path) -> str:
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)


def find_release_files(root: Path, extra_paths: list[Path] | None = None) -> list[Path]:
    cands = []
    for base in [root, *(extra_paths or [])]:
        for rel in ("odoo/release.py", "odoo/odoo/release.py", "src/odoo/odoo/release.py", "server/odoo/release.py"):
            p = base / rel
            if p.is_file():
                cands.append(p)
    return cands


def detect(root: Path | str, extra_paths: list[Path] | None = None, max_files: int = 4000) -> dict:
    root = Path(root).resolve()
    signals: list[dict] = []

    for rp in find_release_files(root, extra_paths):
        m = _RELEASE_RE.search(rp.read_text(encoding="utf-8", errors="ignore"))
        if m:
            signals.append({"source": "release_py", "weight": 100, "version": _series(int(m.group(1)), int(m.group(2)) if int(m.group(1)) < 100 else 0),
                            "evidence": _rel(root, rp)})

    count = 0
    manifest_votes: Counter = Counter()
    manifest_examples: dict[str, str] = {}
    fingerprints: list[dict] = []
    rules = [r for r in knowledge()["rules"] if r.get("fingerprint")]
    compiled = [(r, re.compile(r["pattern"], re.M)) for r in rules]

    for p in iter_files(root):
        count += 1
        if count > max_files:
            break
        name = p.name
        try:
            if name in ("Dockerfile",) or name.startswith("Dockerfile") or name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
                text = p.read_text(encoding="utf-8", errors="ignore")
                for i, line in enumerate(text.splitlines(), 1):
                    m = _DOCKER_RE.search(line)
                    if m:
                        signals.append({"source": "docker", "weight": 80, "version": _series(int(m.group(1)), int(m.group(2) or 0)),
                                        "evidence": f"{_rel(root, p)}:{i}"})
            elif name in ("requirements.txt", ".odoo-version", "odoo_version", ".python-version-odoo"):
                text = p.read_text(encoding="utf-8", errors="ignore")
                if name == "requirements.txt":
                    m = _REQ_RE.search(text)
                    if m:
                        signals.append({"source": "config", "weight": 60, "version": _series(int(m.group(1)), int(m.group(2))), "evidence": _rel(root, p)})
                else:
                    m = re.search(r"(\d+)\.(\d+)", text)
                    if m:
                        signals.append({"source": "config", "weight": 60, "version": _series(int(m.group(1)), int(m.group(2))), "evidence": _rel(root, p)})
            elif name == "__manifest__.py":
                text = p.read_text(encoding="utf-8", errors="ignore")
                m = _MANIFEST_VER_RE.search(text)
                if m and 8 <= int(m.group(1)) <= 40:
                    v = _series(int(m.group(1)), int(m.group(2)))
                    manifest_votes[v] += 1
                    manifest_examples.setdefault(v, _rel(root, p))
            if p.suffix in (".py", ".xml", ".js", ".csv") and p.stat().st_size < 600_000:
                text = None
                for rule, rx in compiled:
                    if not any(p.match(g) for g in rule["files"]):
                        continue
                    text = text if text is not None else p.read_text(encoding="utf-8", errors="ignore")
                    m = rx.search(text)
                    if m:
                        line = text.count("\n", 0, m.start()) + 1
                        fingerprints.append({"rule": rule["id"], "since": rule["since"], "kind": rule["fingerprint"],
                                             "evidence": f"{_rel(root, p)}:{line}"})
        except OSError:
            continue

    if manifest_votes:
        v, n = manifest_votes.most_common(1)[0]
        total = sum(manifest_votes.values())
        signals.append({"source": "manifest", "weight": 40 if n / total >= 0.6 else 20, "version": v,
                        "evidence": f"{n}/{total} manifests, e.g. {manifest_examples[v]}",
                        "distribution": dict(manifest_votes)})

    # Fingerprints give bounds: ">=since" means version >= since; "<since" means version < since.
    lower, upper = None, None
    seen_rules = {}
    for fp in fingerprints:
        seen_rules.setdefault(fp["rule"], fp)
    for fp in seen_rules.values():
        s = version_tuple(fp["since"])
        if fp["kind"] == ">=since":
            lower = max(lower or s, s)
        elif fp["kind"] == "<since":
            upper = min(upper or s, s)

    verdict = _decide(signals, lower, upper)
    verdict["fingerprints"] = list(seen_rules.values())[:40]
    verdict["bounds"] = {"min_inclusive": ".".join(map(str, lower)) if lower else None,
                         "max_exclusive": ".".join(map(str, upper)) if upper else None}
    verdict["signals"] = signals
    verdict["files_scanned"] = min(count, max_files)
    return _apply_confirmation(root, verdict)


def _in_bounds(v: str, lower, upper) -> bool:
    t = version_tuple(v)
    return (lower is None or t >= lower) and (upper is None or t < upper)


def _decide(signals: list[dict], lower, upper) -> dict:
    score: Counter = Counter()
    for s in signals:
        score[s["version"]] += s["weight"]
    conflicts = []
    strong = {s["version"] for s in signals if s["weight"] >= 60}
    if len(strong) > 1:
        conflicts.append({"type": "strong_signals_disagree", "versions": sorted(strong, key=version_tuple),
                          "detail": [s for s in signals if s["weight"] >= 60]})
    if lower and upper and lower >= upper:
        conflicts.append({"type": "mixed_syntax", "detail": "Code contains syntax from both before and after a breaking change (partially migrated code?)"})

    version = None
    confidence = "none"
    if score:
        version, best = score.most_common(1)[0]
        rel = [s for s in signals if s["source"] == "release_py"]
        if rel:  # the Odoo source itself is authoritative; other signals only produce conflicts
            version, best = rel[0]["version"], max(best, 100)
        if not _in_bounds(version, lower, upper) and best < 100:
            conflicts.append({"type": "syntax_contradicts_declared_version", "version": version,
                              "bounds": [lower, upper]})
        confidence = "high" if best >= 80 and not conflicts else "medium" if best >= 40 else "low"
    else:
        # Only fingerprints: infer the narrowest series within bounds.
        cands = [v for v in known_series() if _in_bounds(v, lower, upper)]
        if cands and (lower or upper):
            if len(cands) == 1:
                version, confidence = cands[0], "low"
            else:
                version, confidence = None, "low"
        return {"version": version, "confidence": confidence, "candidates": cands, "conflicts": conflicts,
                "edition_hint": None}
    if conflicts and confidence == "high":
        confidence = "medium"
    return {"version": version, "confidence": confidence,
            "candidates": [v for v, _ in score.most_common()], "conflicts": conflicts}


def confirm(root: Path | str, series: str) -> dict:
    """Record a user-confirmed target series in .odoo-master/config.yaml (key confirmed_odoo_version) and
    refresh odoo-version.json. Detection keeps reporting the signals; conflicts move to resolved_conflicts."""
    from . import known_series
    from ..util import state_dir, write_json, load_yaml, dump_yaml
    if not re.match(r"^\d+\.0$", series):
        raise ValueError("series must look like 18.0")
    if series not in known_series():
        raise ValueError(f"unknown series {series}; known: {', '.join(known_series())}")
    root = Path(root)
    cfg_path = state_dir(root) / "config.yaml"
    cfg = (load_yaml(cfg_path) or {}) if cfg_path.exists() else {}
    cfg["confirmed_odoo_version"] = series
    cfg_path.write_text(dump_yaml(cfg), encoding="utf-8")
    res = detect(root)
    write_json(state_dir(root) / "odoo-version.json", res)
    return {"confirmed": series, "config": str(cfg_path), "detected": res.get("detected_version"), "resolved_conflicts": res.get("resolved_conflicts")}


def _apply_confirmation(root: Path, verdict: dict) -> dict:
    from ..util import STATE_DIR_NAME, load_yaml
    p = root / STATE_DIR_NAME / "config.yaml"
    try:
        confirmed = (load_yaml(p) or {}).get("confirmed_odoo_version") if p.exists() else None
    except Exception:
        confirmed = None
    if confirmed:
        verdict["detected_version"] = verdict.get("version")
        verdict["version"] = confirmed
        verdict["confidence"] = "confirmed"
        verdict["resolved_conflicts"] = verdict.get("conflicts") or []
        verdict["conflicts"] = []
    return verdict


def brief(result: dict) -> str:
    v = result.get("version") or "unknown"
    c = result.get("confidence")
    srcs = ", ".join(sorted({s["source"] for s in result.get("signals", [])})) or "fingerprints only"
    out = f"Odoo {v} (confidence {c}; signals: {srcs})"
    if result.get("conflicts"):
        out += f" CONFLICTS: {len(result['conflicts'])} — confirm the version before changing code"
    return out
