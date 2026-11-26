"""Static validation of Odoo modules. Pure static analysis: it never imports Odoo.

Checks (rule ids in brackets) — every finding has severity, rule, file, line, message, fix:
  manifest  [manifest-parse, manifest-name, manifest-license, manifest-data-missing, manifest-depends-unknown,
             manifest-version-series, manifest-asset-missing, data-file-unlisted]
  python    [py-syntax, py-sql-injection, py-eval, py-removed-api-decorator, py-override-no-super,
             py-print, py-sudo-public-route]
  xml       [xml-parse, xml-view-target, xml-ref-module-not-in-depends, xml-duplicate-id, xml-ref-unknown-local]
  security  [acl-header, acl-perm-value, acl-missing-model, acl-group-ref, acl-not-in-manifest, rule-domain-syntax]
  js        [js-syntax] (only when node is available)
  version   [<rule id from knowledge/odoo-versions.yaml>] for the target version
"""
from __future__ import annotations

import ast
import glob
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

from . import knowledge, standard_modules, dependency_closure
from .inventory import find_modules, parse_acl_csv, parse_manifest, classify_module_location
from ..util import iter_files, version_tuple

LICENSES = {"GPL-2", "GPL-2 or any later version", "GPL-3", "GPL-3 or any later version", "AGPL-3", "LGPL-3",
            "Other OSI approved licence", "OEEL-1", "OPL-1", "Other proprietary"}
ACL_HEADER_LEGACY = ["id", "name", "model_id:id", "group_id:id", "perm_read", "perm_write", "perm_create", "perm_unlink"]
ACL_HEADER_20 = ["id", "name", "model_id", "group_id/id", "operation", "domain"]


def F(sev, rule, file, line, msg, fix=None):
    return {"severity": sev, "rule": rule, "file": str(file), "line": line, "message": msg, "fix": fix}


# ----------------------------------------------------------------- manifest
def check_manifest(mod: Path, root: Path, series: str | None, known_modules: set[str]) -> tuple[list, dict | None]:
    out = []
    mpath = mod / "__manifest__.py"
    rel = mpath.relative_to(root)
    manifest, err = parse_manifest(mpath)
    if err or manifest is None:
        return [F("error", "manifest-parse", rel, 1, f"Manifest cannot be parsed: {err}", "Make __manifest__.py a single dict literal.")], None
    if not manifest.get("name"):
        out.append(F("error", "manifest-name", rel, 1, "Manifest has no 'name'.", "Add a human readable 'name'."))
    lic = manifest.get("license")
    if lic is None:
        out.append(F("warning", "manifest-license", rel, 1, "No 'license' key (defaults to LGPL-3).", "Declare the license explicitly."))
    elif lic not in LICENSES:
        out.append(F("error", "manifest-license", rel, 1, f"License '{lic}' is not an accepted value.", f"Use one of: {', '.join(sorted(LICENSES))}"))
    ver = manifest.get("version")
    if series and ver:
        parts = str(ver).split(".")
        if len(parts) >= 4 and ".".join(parts[:2]) != series:
            out.append(F("warning", "manifest-version-series", rel, 1, f"Version '{ver}' does not start with the target series {series}.",
                         f"Use '{series}.x.y.z' and bump it when data or schema changes (needed for upgrade scripts)."))
    listed = set()
    for key in ("data", "demo"):
        for f in manifest.get(key) or []:
            listed.add(f)
            if not (mod / f).exists():
                out.append(F("error", "manifest-data-missing", rel, 1, f"'{key}' references missing file {f}.", "Create the file or remove the entry."))
    for bundle, items in (manifest.get("assets") or {}).items():
        for item in items:
            path = item[-1] if isinstance(item, (list, tuple)) else item
            if not isinstance(path, str) or path.startswith(("http", "/")):
                continue
            if path.split("/")[0] == mod.name:
                pattern = str(mod.parent / path)
                if not glob.glob(pattern, recursive=True):
                    out.append(F("error", "manifest-asset-missing", rel, 1, f"Asset in {bundle} matches no file: {path}", None))
    std = set(standard_modules(series)) | set(knowledge().get("standard_modules", [])) | set(knowledge().get("enterprise_modules", []))
    for d in manifest.get("depends") or []:
        if d not in known_modules and d not in std:
            out.append(F("info", "manifest-depends-unknown", rel, 1,
                         f"Dependency '{d}' is not in this repository nor in the known standard module list.",
                         "Check the addons path (OCA / third-party repo?) — cannot be verified statically."))
    # data files present but never loaded
    for sub in ("views", "security", "data", "report", "wizard"):
        d = mod / sub
        if d.is_dir():
            for p in d.rglob("*"):
                if p.suffix in (".xml", ".csv") and str(p.relative_to(mod)) not in listed:
                    if sub == "wizard" and p.suffix != ".xml":
                        continue
                    out.append(F("warning", "data-file-unlisted", p.relative_to(root), 1,
                                 f"{p.relative_to(mod)} is not listed in the manifest 'data' and will never be loaded.",
                                 "Add it to 'data' (security files first, then views/menus) or delete it."))
    return out, manifest


# ----------------------------------------------------------------- python
_SQL_EXEC = re.compile(r"\.execute\(\s*(f[\"']|[\"'][^\"']*[\"']\s*%|[\"'][^\"']*[\"']\s*\.format\()")
_REMOVED_DECOS = {"api.multi", "api.one", "api.cr", "api.cr_uid", "api.v7", "api.v8", "api.returns_one"}


def check_python(path: Path, root: Path) -> list:
    out = []
    rel = path.relative_to(root)
    text = path.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        return [F("error", "py-syntax", rel, exc.lineno or 1, f"Syntax error: {exc.msg}", None)]
    for i, line in enumerate(text.splitlines(), 1):
        if _SQL_EXEC.search(line):
            out.append(F("error", "py-sql-injection", rel, i, "SQL built with string formatting passed to execute().",
                         "Pass parameters separately: cr.execute(query, params), or use odoo.tools.SQL (17+)."))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "eval":
            out.append(F("error", "py-eval", rel, node.lineno, "eval() on data is unsafe.", "Use ast.literal_eval or odoo.tools.safe_eval for trusted admin data only."))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print" and "tests" not in rel.parts:
            out.append(F("info", "py-print", rel, node.lineno, "print() in module code.", "Use _logger = logging.getLogger(__name__)."))
        if isinstance(node, ast.ClassDef):
            is_ext = any(isinstance(s, ast.Assign) and any(getattr(t, "id", "") == "_inherit" for t in s.targets) for s in node.body)
            for fn in node.body:
                if not isinstance(fn, ast.FunctionDef):
                    continue
                routes_public = False
                decos = []
                for d in fn.decorator_list:
                    target = d.func if isinstance(d, ast.Call) else d
                    name = ast.unparse(target) if hasattr(ast, "unparse") else ""
                    decos.append(name)
                    if name in _REMOVED_DECOS:
                        out.append(F("error", "py-removed-api-decorator", rel, fn.lineno, f"@{name} was removed from Odoo (13.0+).", "Remove it; methods are recordset-aware by default."))
                    if name.endswith("route") and isinstance(d, ast.Call):
                        for kw in d.keywords:
                            if kw.arg == "auth" and isinstance(kw.value, ast.Constant) and kw.value.value in ("public", "none"):
                                routes_public = True
                if is_ext and fn.name in ("create", "write", "unlink", "copy", "default_get", "action_confirm", "action_post", "button_validate"):
                    calls_super = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                                      and isinstance(n.func.value, ast.Call) and getattr(n.func.value.func, "id", "") == "super"
                                      for n in ast.walk(fn))
                    if not calls_super:
                        out.append(F("error", "py-override-no-super", rel, fn.lineno, f"Override of {fn.name}() on an inherited model does not call super().",
                                     "Call super() so standard behaviour and other modules' overrides still run."))
                if routes_public and "sudo()" in (ast.get_source_segment(text, fn) or ""):
                    out.append(F("warning", "py-sudo-public-route", rel, fn.lineno, "sudo() inside a public/none-auth route.",
                                 "Restrict the domain/fields explicitly; never sudo() over user-supplied ids or domains."))
    return out


# ----------------------------------------------------------------- xml
def _parse_xml(path: Path):
    """Prefer lxml (gives line numbers); fall back to ElementTree."""
    try:
        from lxml import etree as LET  # type: ignore
        try:
            return LET.parse(str(path), LET.XMLParser(remove_comments=True)), None
        except LET.XMLSyntaxError as exc:
            return None, (exc.lineno or 1, str(exc))
    except ImportError:
        try:
            return ET.parse(path), None
        except ET.ParseError as exc:
            return None, (getattr(exc, "position", (1, 0))[0], str(exc))


def check_xml(path: Path, root: Path, module: str, depends: set[str], local_ids: set[str]) -> list:
    """`depends` must be the transitive dependency closure of the module."""
    out = []
    rel = path.relative_to(root)
    tree, err = _parse_xml(path)
    if err:
        return [F("error", "xml-parse", rel, err[0], f"XML is not well-formed: {err[1]}", None)]
    seen = set()
    for el in tree.iter():
        if not isinstance(el.tag, str):
            continue
        line = getattr(el, "sourceline", None)
        xid = el.get("id") if el.tag in ("record", "menuitem", "template") else None
        if xid:
            if xid in seen:
                out.append(F("error", "xml-duplicate-id", rel, line, f"Duplicate XML id '{xid}' in file.", None))
            seen.add(xid)
        refs = []
        if el.tag == "field" and el.get("ref"):
            refs.append(el.get("ref"))
        if el.tag == "menuitem":
            refs += [el.get(a) for a in ("parent", "action") if el.get(a)]
        if el.tag == "template" and el.get("inherit_id"):
            refs.append(el.get("inherit_id"))
        for attr in ("groups",):
            if el.get(attr) and el.tag in ("menuitem", "field", "button", "record", "template", "page", "group", "div"):
                refs += [g.strip().lstrip("!") for g in el.get(attr).split(",") if g.strip()]
        for r in refs:
            if "." in r:
                mod = r.split(".", 1)[0]
                if mod != module and mod not in depends and mod != "base":
                    out.append(F("error", "xml-ref-module-not-in-depends", rel, line,
                                 f"Reference '{r}' points to module '{mod}', which is not in the (transitive) dependencies.",
                                 f"Add '{mod}' to depends (or a module that depends on it)."))
            elif r not in local_ids and not r.startswith("model_"):
                out.append(F("warning", "xml-ref-unknown-local", rel, line, f"Reference '{r}' is not defined in this module's XML files.",
                             "Qualify it as module.xml_id or define it before use."))
        if el.tag == "record" and el.get("model") == "ir.ui.view":
            names = {f.get("name") for f in el.findall("field")}
            if "inherit_id" not in names and "model" not in names and el.find("field[@name='arch']") is not None:
                arch = el.find("field[@name='arch']")
                if len(arch) and arch[0].tag not in ("t", "templates"):
                    out.append(F("warning", "xml-view-target", rel, line, f"View '{el.get('id')}' has neither 'model' nor 'inherit_id'.", None))
            if "inherit_id" in names:
                arch = el.find("field[@name='arch']")
                if arch is not None:
                    for xp in arch.iter("xpath"):
                        if not xp.get("expr"):
                            out.append(F("error", "xml-view-target", rel, line, f"xpath without expr in '{el.get('id')}'.", None))
                        if xp.get("position") not in (None, "inside", "after", "before", "replace", "attributes", "move"):
                            out.append(F("error", "xml-view-target", rel, line, f"Invalid xpath position '{xp.get('position')}'.", None))
    return out


# ----------------------------------------------------------------- security
def check_security(mod: Path, root: Path, series: str | None, manifest: dict, models_new: list[dict], local_ids: set[str], depends: set[str]) -> list:
    out = []
    data = set(manifest.get("data") or [])
    for name in ("ir.model.access.csv", "ir.access.csv"):
        for p in mod.rglob(name):
            rel = p.relative_to(root)
            if str(p.relative_to(mod)) not in data:
                out.append(F("error", "acl-not-in-manifest", rel, 1, f"{p.name} is not listed in the manifest data.", "Add it to 'data' before the views."))
            first = p.read_text(encoding="utf-8", errors="ignore").splitlines()[:1]
            header = [h.strip() for h in first[0].split(",")] if first else []
            expected = ACL_HEADER_20 if name == "ir.access.csv" else ACL_HEADER_LEGACY
            if header[: len(expected)] != expected:
                out.append(F("error", "acl-header", rel, 1, f"Unexpected header {header}.", f"Expected: {','.join(expected)}"))
                continue
            for row in parse_acl_csv(p):
                if name == "ir.model.access.csv":
                    for perm in ("perm_read", "perm_write", "perm_create", "perm_unlink"):
                        if row.get(perm) not in ("0", "1"):
                            out.append(F("error", "acl-perm-value", rel, row["_line"], f"{perm} must be 0 or 1, got '{row.get(perm)}'.", None))
                    model_ref, group_ref = row.get("model_id:id", ""), row.get("group_id:id", "")
                else:
                    if not set(row.get("operation", "")) <= set("crud") or not row.get("operation"):
                        out.append(F("error", "acl-perm-value", rel, row["_line"], f"operation must be a subset of 'crud', got '{row.get('operation')}'.", None))
                    model_ref, group_ref = row.get("model_id", ""), row.get("group_id/id", "")
                if not model_ref:
                    out.append(F("error", "acl-missing-model", rel, row["_line"], "Row has no model reference.", None))
                if group_ref:
                    gmod = group_ref.split(".", 1)[0] if "." in group_ref else None
                    if gmod is None and group_ref not in local_ids:
                        out.append(F("error", "acl-group-ref", rel, row["_line"], f"Group '{group_ref}' is not defined in this module.", "Use module.xml_id."))
                    elif gmod and gmod not in depends and gmod not in ("base", mod.name):  # depends = closure
                        out.append(F("error", "acl-group-ref", rel, row["_line"], f"Group module '{gmod}' is not in depends.", None))
                elif series and version_tuple(series) < (20,):
                    out.append(F("warning", "acl-group-ref", rel, row["_line"], "ACL without group applies to every user (including portal/public).",
                                 "Set group_id unless global access is really intended."))
    for m in models_new:
        out.append(F("error", "acl-missing-model", m["file"], m["line"], f"Model '{m['model']}' has no access rule; non-admin users cannot use it and Odoo logs a warning.",
                     "Add a row in security/ir.model.access.csv (ir.access.csv on 20.0)."))
    for p in mod.rglob("*.xml"):
        try:
            tree = ET.parse(p)
        except ET.ParseError:
            continue
        for rec in tree.iter("record"):
            if rec.get("model") == "ir.rule":
                dom = rec.find("field[@name='domain_force']")
                if dom is not None and dom.text:
                    try:
                        ast.parse(dom.text.strip(), mode="eval")
                    except SyntaxError as exc:
                        out.append(F("error", "rule-domain-syntax", p.relative_to(root), None, f"Record rule '{rec.get('id')}' domain is not valid Python: {exc.msg}", None))
    return out


# ----------------------------------------------------------------- js
def check_js(files: list[Path], root: Path) -> list:
    node = shutil.which("node")
    if not node or not files:
        return []
    out = []
    with tempfile.TemporaryDirectory() as td:
        for p in files[:300]:
            tmp = Path(td) / (p.stem + ".mjs")
            tmp.write_text(p.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
            r = subprocess.run([node, "--check", str(tmp)], capture_output=True, text=True)
            if r.returncode != 0:
                msg = (r.stderr.strip().splitlines() or ["syntax error"])
                m = re.search(r":(\d+)\n", r.stderr)
                out.append(F("error", "js-syntax", p.relative_to(root), int(m.group(1)) if m else None, msg[-1][:300], None))
    return out


# ----------------------------------------------------------------- version rules
def check_version_rules(mod: Path, root: Path, series: str | None) -> list:
    if not series:
        return []
    out = []
    target = version_tuple(series)
    rules = [r for r in knowledge()["rules"] if r.get("check", True) and version_tuple(r["since"]) <= target and r["severity"] != "info"]
    for p in iter_files(mod):
        if p.suffix not in (".py", ".xml", ".js", ".csv") or "migrations" in p.parts or "upgrades" in p.parts:
            continue
        text = None
        for r in rules:
            if not any(p.match(g) for g in r["files"]):
                continue
            text = text if text is not None else p.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r["pattern"], text, re.M):
                line = text.count("\n", 0, m.start()) + 1
                out.append(F(r["severity"], r["id"], p.relative_to(root), line, r["message"], r.get("doc")))
                if r["pattern"] == ".":
                    break
    return out


# ----------------------------------------------------------------- driver
def validate(root: Path | str, series: str | None = None, modules: list[str] | None = None, files: list[str] | None = None,
             with_js: bool = True) -> dict:
    root = Path(root).resolve()
    all_mods = [m for m in find_modules(root) if classify_module_location(m, root) == "custom"]
    known = {m.name for m in all_mods}
    if modules:
        all_mods = [m for m in all_mods if m.name in modules]
    if files:
        fset = {Path(f).resolve() for f in files}
        all_mods = [m for m in all_mods if any(str(f).startswith(str(m.resolve()) + "/") for f in fset)]
    findings: list[dict] = []
    checked = []
    from .inventory import scan_module
    for mod in all_mods:
        checked.append(mod.name)
        mf, manifest = check_manifest(mod, root, series, known)
        findings += mf
        if manifest is None:
            continue
        custom_graph = {}
        for other in find_modules(root):
            om, _ = parse_manifest(other / "__manifest__.py")
            if om:
                custom_graph[other.name] = list(om.get("depends") or [])
        depends = dependency_closure(manifest.get("depends") or [], series, custom_graph)
        info = scan_module(mod, root)
        local_ids = set(info["xml_ids"])
        for p in iter_files(mod):
            if p.suffix == ".py" and p.name != "__manifest__.py":
                findings += check_python(p, root)
            elif p.suffix == ".xml" and not (len(p.relative_to(mod).parts) > 1 and p.relative_to(mod).parts[0] == "static"):
                findings += check_xml(p, root, mod.name, depends, local_ids)
        acl_models = {r.get("model_id:id") or r.get("model_id") for r in info["acl"]}
        missing = []
        for mdl in info["models"]:
            if mdl["kind"] in ("new", "prototype") and mdl["base"] != "AbstractModel" and mdl["name"]:
                ext = "model_" + mdl["name"].replace(".", "_")
                if not any(a and (a == ext or a.endswith("." + ext) or a == mdl["name"]) for a in acl_models):
                    missing.append({"model": mdl["name"], "file": mdl["file"], "line": mdl["line"]})
        findings += check_security(mod, root, series, manifest, missing, local_ids, depends)
        findings += check_version_rules(mod, root, series)
        if with_js:
            findings += check_js([p for p in iter_files(mod, ["*.js"]) if "lib" not in p.parts], root)
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in ("error", "warning", "info")}
    return {"root": str(root), "series": series, "modules_checked": checked, "counts": counts,
            "passed": counts["error"] == 0, "findings": findings, "level": "static"}
