"""Odoo intelligence: version detection, inventory, validation, migration scanning, runtime, database."""
from functools import lru_cache

from ..util import PLUGIN_ROOT, load_yaml


@lru_cache(maxsize=1)
def knowledge() -> dict:
    return load_yaml(PLUGIN_ROOT / "knowledge" / "odoo-versions.yaml")


def known_series() -> list[str]:
    return sorted(knowledge()["versions"].keys(), key=lambda v: float(v))


def _nearest_series(series: str | None) -> str | None:
    if not series:
        return None
    from ..util import version_tuple
    avail = known_series()
    if series in avail:
        return series
    older = [v for v in avail if version_tuple(v) <= version_tuple(series)]
    return older[-1] if older else avail[0]


@lru_cache(maxsize=8)
def standard_modules(series: str | None) -> dict:
    """{module: [depends]} for Odoo Community of that series (extracted from the official image)."""
    import json
    s = _nearest_series(series) or known_series()[-1]
    p = PLUGIN_ROOT / "knowledge" / "standard-modules" / f"community-{s}.json"
    return json.loads(p.read_text()) if p.exists() else {}


@lru_cache(maxsize=8)
def standard_models(series: str | None) -> dict:
    """{"defined_in": {model: module}, "extended_in": {model: [modules]}} for Odoo Community of that series."""
    import json
    s = _nearest_series(series) or known_series()[-1]
    p = PLUGIN_ROOT / "knowledge" / "standard-modules" / f"models-{s}.json"
    return json.loads(p.read_text()) if p.exists() else {"defined_in": {}, "extended_in": {}}


def dependency_closure(direct: list[str] | set[str], series: str | None, custom_graph: dict | None = None) -> set[str]:
    """Transitive dependencies using the custom module graph first, then the standard graph."""
    std = standard_modules(series)
    graph = {**std, **(custom_graph or {})}
    seen: set[str] = set()
    stack = list(direct)
    while stack:
        m = stack.pop()
        if m in seen:
            continue
        seen.add(m)
        stack.extend(graph.get(m, []))
    return seen
