"""Static inventory of an Odoo code base (no database, no Odoo import required).

Produces the project knowledge model written to .odoo-master/:
  project-inventory.json      modules with manifests, models, views, security, controllers, assets, tests
  module-dependency-map.json  graph, reverse deps, topological order, cycles, unknown dependencies
  architecture-map.json       model -> defining/extending modules, view inheritance, menus/actions
These are *code-level* facts. Database-level facts (installed modules, real schema, data) come
only from odoo_master.odoo.db and are recorded separately.
"""
from __future__ import annotations

import ast
import csv
import io
import re
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

from . import knowledge, standard_modules, standard_models
from ..util import iter_files, now_iso

CORE_MARKERS = ("odoo/addons/base/__manifest__.py", "addons/base/__manifest__.py")


def parse_manifest(path: Path) -> tuple[dict | None, str | None]:
    try:
        node = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
        for stmt in node.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Dict):
                return ast.literal_eval(stmt.value), None
        return None, "manifest does not contain a dict literal"
    except (SyntaxError, ValueError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def find_modules(root: Path) -> list[Path]:
    mods = []
    for p in iter_files(root, ["__manifest__.py", "__openerp__.py"]):
        mods.append(p.parent)
    return sorted(set(mods))


def classify_module_location(mod: Path, root: Path) -> str:
    """'core' for Odoo Community source, 'enterprise' for enterprise checkouts, else 'custom'."""
    parts = mod.resolve().parts
    rel = str(mod.relative_to(root)) if mod.is_relative_to(root) else str(mod)
    if "enterprise" in parts and (mod.parent / "web_enterprise").exists():
        return "enterprise"
    for anc in [mod.parent, *mod.parent.parents]:
        if (anc / "base" / "__manifest__.py").exists() and (anc.parent / "release.py").exists():
            return "core"
        if (anc / "odoo-bin").exists() and rel.startswith(("odoo/", "addons/", "odoo/addons/")):
            return "core"
        if anc == root:
            break
    return "custom"


# ------------------------------------------------------------------ python models
_FIELD_CALL = re.compile(r"^fields\.(\w+)$")


def _const(node):
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _dotted(node) -> str:
    if isinstance(node, ast.Attribute):
        return _dotted(node.value) + "." + node.attr
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Call):
        return _dotted(node.func)
    return ""


def parse_python(path: Path, root: Path) -> dict:
    out = {"models": [], "controllers": [], "syntax_error": None}
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
    except SyntaxError as exc:
        out["syntax_error"] = f"{exc.msg} at line {exc.lineno}"
        return out
    rel = str(path.relative_to(root))
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        bases = [_dotted(b) for b in cls.bases]
        attrs, fields, methods, constraints = {}, [], [], []
        for st in cls.body:
            if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
                tname = st.targets[0].id
                if tname in ("_name", "_inherit", "_inherits", "_description", "_order", "_rec_name", "_table",
                             "_sql_constraints", "_auto", "_transient", "_check_company_auto", "_parent_store"):
                    attrs[tname] = _const(st.value) if tname != "_sql_constraints" else "present"
                elif isinstance(st.value, ast.Call):
                    fname = _dotted(st.value.func)
                    m = _FIELD_CALL.match(fname)
                    if m:
                        kw = {k.arg: _const(k.value) if not isinstance(k.value, (ast.Lambda, ast.Name, ast.Attribute)) else f"<{type(k.value).__name__.lower()}>"
                              for k in st.value.keywords if k.arg}
                        comodel = _const(st.value.args[0]) if st.value.args and m.group(1) in ("Many2one", "One2many", "Many2many") else kw.get("comodel_name")
                        fields.append({"name": tname, "type": m.group(1), "line": st.lineno,
                                       "comodel": comodel,
                                       "compute": kw.get("compute"), "related": kw.get("related"),
                                       "store": kw.get("store"), "required": kw.get("required"),
                                       "index": kw.get("index"), "groups": kw.get("groups")})
                    elif fname in ("models.Constraint", "models.Index", "models.UniqueIndex"):
                        constraints.append({"name": tname, "kind": fname.split(".")[-1], "line": st.lineno})
            elif isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decos = [_dotted(d) for d in st.decorator_list]
                calls_super = any(isinstance(n, ast.Call) and _dotted(n.func).startswith("super") for n in ast.walk(st))
                methods.append({"name": st.name, "line": st.lineno, "decorators": decos, "calls_super": calls_super})
        is_model = any(b.startswith("models.") and b.split(".")[-1] in ("Model", "TransientModel", "AbstractModel") for b in bases)
        if is_model and ("_name" in attrs or "_inherit" in attrs):
            inherit = attrs.get("_inherit")
            inherit_list = [inherit] if isinstance(inherit, str) else list(inherit or [])
            name = attrs.get("_name")
            kind = "new" if name and (not inherit_list or name not in inherit_list) else "extension"
            if name and inherit_list and name not in inherit_list:
                kind = "prototype"
            out["models"].append({
                "class": cls.name, "file": rel, "line": cls.lineno,
                "base": next((b.split(".")[-1] for b in bases if b.startswith("models.")), None),
                "name": name or (inherit_list[0] if len(inherit_list) == 1 else None),
                "inherit": inherit_list, "inherits": attrs.get("_inherits"), "kind": kind,
                "description": attrs.get("_description"), "has_sql_constraints": "_sql_constraints" in attrs,
                "fields": fields, "methods": methods, "constraints": constraints,
            })
        if any(b.endswith("Controller") for b in bases):
            routes = []
            for st in cls.body:
                if isinstance(st, ast.FunctionDef):
                    for d in st.decorator_list:
                        if isinstance(d, ast.Call) and _dotted(d.func).endswith("route"):
                            kw = {k.arg: _const(k.value) for k in d.keywords if k.arg}
                            urls = _const(d.args[0]) if d.args else kw.get("route")
                            routes.append({"method": st.name, "line": st.lineno, "routes": urls,
                                           "type": kw.get("type", "http"), "auth": kw.get("auth", "user"),
                                           "csrf": kw.get("csrf"), "methods": kw.get("methods")})
            out["controllers"].append({"class": cls.name, "file": rel, "routes": routes})
    return out


# ------------------------------------------------------------------ xml
def parse_xml(path: Path, root: Path) -> dict:
    rel = str(path.relative_to(root))
    out = {"views": [], "actions": [], "menus": [], "rules": [], "groups": [], "records": 0, "xml_ids": [],
           "templates": [], "crons": [], "error": None}
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        out["error"] = str(exc)
        return out
    for el in tree.iter():
        tag = el.tag
        if tag == "record":
            out["records"] += 1
            model, xid = el.get("model"), el.get("id")
            if xid:
                out["xml_ids"].append(xid)
            fields = {f.get("name"): (f.get("ref") or f.get("eval") or (f.text or "").strip()) for f in el.findall("field")}
            if model == "ir.ui.view":
                arch = el.find("field[@name='arch']")
                vtype = None
                if arch is not None and len(arch):
                    vtype = arch[0].tag if arch[0].tag not in ("xpath", "data") else None
                out["views"].append({"id": xid, "file": rel, "model": fields.get("model"),
                                     "inherit_id": fields.get("inherit_id"), "type": vtype,
                                     "priority": fields.get("priority")})
            elif model in ("ir.actions.act_window", "ir.actions.server", "ir.actions.report", "ir.actions.client"):
                out["actions"].append({"id": xid, "type": model, "res_model": fields.get("res_model") or fields.get("model_id"),
                                       "view_mode": fields.get("view_mode")})
            elif model == "ir.rule":
                out["rules"].append({"id": xid, "model": fields.get("model_id"), "domain": fields.get("domain_force"),
                                     "groups": fields.get("groups"), "global": "groups" not in fields})
            elif model == "res.groups":
                out["groups"].append({"id": xid, "name": fields.get("name")})
            elif model == "ir.cron":
                out["crons"].append({"id": xid, "model": fields.get("model_id"), "code": fields.get("code")})
        elif tag == "menuitem":
            out["menus"].append({"id": el.get("id"), "parent": el.get("parent"), "action": el.get("action"),
                                 "groups": el.get("groups")})
            if el.get("id"):
                out["xml_ids"].append(el.get("id"))
        elif tag == "template":
            out["templates"].append({"id": el.get("id"), "inherit_id": el.get("inherit_id")})
            if el.get("id"):
                out["xml_ids"].append(el.get("id"))
    return out


def parse_acl_csv(path: Path) -> list[dict]:
    rows = []
    text = path.read_text(encoding="utf-8", errors="ignore")
    for i, row in enumerate(csv.DictReader(io.StringIO(text)), 2):
        row = {k.strip() if k else k: (v or "").strip() for k, v in row.items()}
        row["_line"] = i
        rows.append(row)
    return rows


# ------------------------------------------------------------------ module scan
def scan_module(mod: Path, root: Path) -> dict:
    mpath = mod / "__manifest__.py"
    if not mpath.exists():
        mpath = mod / "__openerp__.py"
    manifest, err = parse_manifest(mpath)
    info = {
        "name": mod.name, "path": str(mod.relative_to(root)) if mod.is_relative_to(root) else str(mod),
        "location": classify_module_location(mod, root), "manifest_error": err,
        "manifest": {k: manifest.get(k) for k in ("name", "version", "depends", "license", "category",
                                                   "application", "auto_install", "installable", "author",
                                                   "data", "demo", "assets", "external_dependencies",
                                                   "pre_init_hook", "post_init_hook", "uninstall_hook")} if manifest else None,
        "models": [], "controllers": [], "views": [], "actions": [], "menus": [], "rules": [], "groups": [],
        "templates": [], "crons": [], "acl": [], "acl_format": None, "xml_ids": [], "syntax_errors": [],
        "xml_errors": [], "js_files": 0, "owl_components": 0, "scss_files": 0, "tests": {"python": 0, "js": 0, "tours": 0},
        "migrations": [], "has_i18n": (mod / "i18n").is_dir(), "file_count": 0,
    }
    for p in iter_files(mod):
        info["file_count"] += 1
        rel_in_mod = p.relative_to(mod)
        suffix = p.suffix
        if suffix == ".py" and p.name not in ("__manifest__.py", "__openerp__.py"):
            if rel_in_mod.parts[0] in ("migrations", "upgrades"):
                continue
            res = parse_python(p, root)
            if res["syntax_error"]:
                info["syntax_errors"].append({"file": str(p.relative_to(root)), "error": res["syntax_error"]})
            info["models"].extend(res["models"])
            info["controllers"].extend(res["controllers"])
            if rel_in_mod.parts[0] == "tests" and p.name.startswith("test_"):
                info["tests"]["python"] += 1
        elif suffix == ".xml" and "static" not in rel_in_mod.parts[:1]:
            res = parse_xml(p, root)
            if res["error"]:
                info["xml_errors"].append({"file": str(p.relative_to(root)), "error": res["error"]})
            for k in ("views", "actions", "menus", "rules", "groups", "templates", "crons", "xml_ids"):
                info[k].extend(res[k])
        elif suffix == ".csv" and p.name in ("ir.model.access.csv", "ir.access.csv"):
            info["acl_format"] = "ir.access" if p.name == "ir.access.csv" else "ir.model.access"
            info["acl"].extend(dict(r, _file=str(p.relative_to(root))) for r in parse_acl_csv(p))
        elif suffix in (".js", ".mjs", ".ts"):
            info["js_files"] += 1
            if "tests" in rel_in_mod.parts:
                info["tests"]["js"] += 1
                if "tours" in rel_in_mod.parts:
                    info["tests"]["tours"] += 1
            else:
                try:
                    t = p.read_text(encoding="utf-8", errors="ignore")
                    info["owl_components"] += len(re.findall(r"extends\s+Component\b", t))
                except OSError:
                    pass
        elif suffix == ".scss":
            info["scss_files"] += 1
    for mdir in ("migrations", "upgrades"):
        d = mod / mdir
        if d.is_dir():
            for vd in sorted(x for x in d.iterdir() if x.is_dir()):
                info["migrations"].append({"version": vd.name, "scripts": sorted(f.name for f in vd.glob("*.py"))})
    return info


def dependency_map(modules: dict[str, dict], series: str | None = None) -> dict:
    k = knowledge()
    std = set(standard_modules(series)) | set(k.get("standard_modules", [])) | set(k.get("enterprise_modules", []))
    ent = set(k.get("enterprise_modules", []))
    graph = {n: list((m.get("manifest") or {}).get("depends") or []) for n, m in modules.items()}
    reverse = defaultdict(list)
    unknown, enterprise_deps = defaultdict(list), defaultdict(list)
    for n, deps in graph.items():
        for d in deps:
            reverse[d].append(n)
            if d not in modules and d not in std:
                unknown[n].append(d)
            if d in ent:
                enterprise_deps[n].append(d)
    # Tarjan SCC for cycles + Kahn topological order over project modules
    index, low, stack, on, cycles, counter = {}, {}, [], set(), [], [0]

    def strong(v):
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on.add(v)
        for w in graph.get(v, []):
            if w not in graph:
                continue
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1 or v in graph.get(v, []):
                cycles.append(sorted(comp))

    for v in graph:
        if v not in index:
            strong(v)
    indeg = {n: sum(1 for d in graph[n] if d in graph) for n in graph}
    queue = sorted(n for n, d in indeg.items() if d == 0)
    order = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for r in sorted(reverse.get(n, [])):
            if r in indeg:
                indeg[r] -= 1
                if indeg[r] == 0:
                    queue.append(r)
    return {"graph": graph, "reverse": {k2: sorted(v) for k2, v in reverse.items()}, "install_order": order,
            "cycles": cycles, "unknown_dependencies": dict(unknown), "enterprise_dependencies": dict(enterprise_deps),
            "external_standard_dependencies": sorted({d for deps in graph.values() for d in deps if d not in modules})}


def architecture_map(modules: dict[str, dict], series: str | None = None) -> dict:
    std_models = standard_models(series)
    models = defaultdict(lambda: {"defined_in": [], "extended_in": [], "fields_added": defaultdict(list), "views": []})
    for n, m in modules.items():
        for mdl in m["models"]:
            key = mdl["name"] or "?"
            if mdl["kind"] in ("new", "prototype"):
                models[key]["defined_in"].append(n)
            else:
                models[key]["extended_in"].append(n)
            for f in mdl["fields"]:
                models[key]["fields_added"][n].append(f["name"])
        for v in m["views"]:
            if v.get("model"):
                models[v["model"]]["views"].append({"module": n, "id": v["id"], "inherit_id": v.get("inherit_id"), "type": v.get("type")})
    out = {}
    for k, v in models.items():
        out[k] = {"defined_in": v["defined_in"], "extended_in": v["extended_in"],
                  "standard_model_extended": not v["defined_in"],
                  "standard_defined_in": std_models["defined_in"].get(k),
                  "standard_extended_in": std_models["extended_in"].get(k, [])[:25],
                  "fields_added": dict(v["fields_added"]), "views": v["views"]}
    return {"models": out}


def scan(root: Path | str, include_core: bool = False, series: str | None = None) -> dict:
    root = Path(root).resolve()
    mods = find_modules(root)
    modules: dict[str, dict] = {}
    core_present, core_paths = False, set()
    for mod in mods:
        loc = classify_module_location(mod, root)
        if loc in ("core", "enterprise"):
            core_present = True
            core_paths.add(str(mod.parent.relative_to(root)) if mod.parent.is_relative_to(root) else str(mod.parent))
            if not include_core:
                continue
        info = scan_module(mod, root)
        if info["name"] in modules:
            info["duplicate_of"] = modules[info["name"]]["path"]
            info["name"] = f"{info['name']}@{info['path']}"
        modules[info["name"]] = info
    addons_paths = sorted({m["path"].rsplit("/", 1)[0] if "/" in m["path"] else "." for m in modules.values()})
    deps = dependency_map(modules, series)
    arch = architecture_map(modules, series)
    # Models without ACLs (new models only; transient models need ACLs from 14+ as well)
    missing_acl = []
    for n, m in modules.items():
        acl_models = {r.get("model_id:id") or r.get("model_id/id") or r.get("model_id") for r in m["acl"]}
        for mdl in m["models"]:
            if mdl["kind"] in ("new", "prototype") and mdl["base"] != "AbstractModel" and mdl["name"]:
                ext_id = "model_" + mdl["name"].replace(".", "_")
                if not any(a and (a == ext_id or a.endswith("." + ext_id) or a == mdl["name"]) for a in acl_models):
                    missing_acl.append({"module": n, "model": mdl["name"], "file": mdl["file"], "line": mdl["line"]})
    return {
        "generated_at": now_iso(),
        "root": str(root),
        "knowledge_level": "code",
        "series_used_for_standard_knowledge": series,
        "addons_paths": addons_paths,
        "odoo_core_in_repo": core_present,
        "protected_core_paths": sorted(core_paths),
        "module_count": len(modules),
        "modules": modules,
        "dependencies": deps,
        "architecture": arch,
        "findings": {
            "models_missing_acl": missing_acl,
            "syntax_errors": [e for m in modules.values() for e in m["syntax_errors"]],
            "xml_errors": [e for m in modules.values() for e in m["xml_errors"]],
            "manifest_errors": [{"module": n, "error": m["manifest_error"]} for n, m in modules.items() if m["manifest_error"]],
            "dependency_cycles": deps["cycles"],
            "unknown_dependencies": deps["unknown_dependencies"],
            "modules_without_tests": sorted(n for n, m in modules.items() if not (m["tests"]["python"] or m["tests"]["js"])),
        },
    }


def summary(inv: dict) -> dict:
    mods = inv["modules"]
    return {
        "module_count": inv["module_count"],
        "addons_paths": inv["addons_paths"],
        "odoo_core_in_repo": inv["odoo_core_in_repo"],
        "modules": {n: {"version": (m["manifest"] or {}).get("version"), "depends": (m["manifest"] or {}).get("depends"),
                        "models": len(m["models"]), "views": len(m["views"]), "tests": m["tests"]["python"] + m["tests"]["js"]}
                    for n, m in mods.items()},
        "findings": {k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in inv["findings"].items()},
    }
