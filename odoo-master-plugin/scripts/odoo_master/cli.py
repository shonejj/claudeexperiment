"""`odoo-master` command line. Every command prints JSON (or a brief line with --brief).

The plugin's bin/odoo-master wrapper puts this on PATH while the plugin is enabled, so skills and
agents call e.g. `odoo-master analyze --brief`. Exit codes: 0 ok, 1 findings/failure, 2 usage error,
3 refused by policy.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .util import emit, find_project_root, state_dir


def _root(a) -> Path:
    return Path(a.root).resolve() if getattr(a, "root", None) else find_project_root()


def _csv(v):
    return [x.strip() for x in v.split(",") if x.strip()] if v else None


def cmd_analyze(a):
    from .project import analyze
    res = analyze(_root(a), write=not a.no_write, include_core=a.include_core)
    if a.brief:
        p = res["project"]
        f = res["inventory"]["findings"]
        print(f"{p['odoo']['version'] or 'unknown'} ({p['odoo']['confidence']}) | modules={res['inventory']['module_count']} "
              f"| missing_acl={len(f['models_missing_acl'])} syntax_errors={len(f['syntax_errors'])} xml_errors={len(f['xml_errors'])} "
              f"| written to {state_dir(_root(a))}")
    else:
        emit({"project": res["project"], "findings": res["inventory"]["findings"], "version": res["version"]})
    return 0


def cmd_detect_version(a):
    from .odoo.version import detect, brief
    res = detect(_root(a))
    if a.brief:
        print(brief(res))
    else:
        emit(res)
    return 0 if res.get("version") else 1


def cmd_inventory(a):
    from .odoo.inventory import scan, summary
    inv = scan(_root(a), include_core=a.include_core)
    emit(summary(inv) if a.summary else inv)
    return 0


def _series_for(a):
    if getattr(a, "series", None):
        return a.series
    from .odoo.version import detect
    from .config import load_config
    v = detect(_root(a)).get("version")
    return v or load_config(_root(a)).get("default_odoo_version") or None


def cmd_validate(a):
    from .odoo.validate import validate
    series = _series_for(a)
    res = validate(_root(a), series=series, modules=_csv(a.modules), files=_csv(a.files), with_js=not a.no_js)
    if a.min_severity:
        order = {"info": 0, "warning": 1, "error": 2}
        res["findings"] = [f for f in res["findings"] if order[f["severity"]] >= order[a.min_severity]]
    if a.brief:
        print(f"series={series} modules={len(res['modules_checked'])} errors={res['counts']['error']} warnings={res['counts']['warning']}")
        for f in res["findings"][:40]:
            if f["severity"] != "info":
                print(f"  {f['severity'].upper():7} {f['rule']:32} {f['file']}:{f['line'] or ''} {f['message']}")
    else:
        emit(res)
    return 0 if res["passed"] else 1


def cmd_migration(a):
    from .odoo import migration
    res = migration.scan(_root(a), a.source, a.target, _csv(a.modules))
    if a.action == "plan":
        res = {"scan_totals": res["totals"], "plan": migration.plan_skeleton(res), "scan": res}
    emit(res)
    return 0


def cmd_logs(a):
    from .odoo.logs import summarize_file
    emit(summarize_file(a.file))
    return 0


def cmd_runtime(a):
    from .odoo import runtime
    root = _root(a)
    if a.action == "check":
        emit(runtime.available())
        return 0
    if a.action == "status":
        emit(runtime.status(root))
        return 0
    if a.action == "stop":
        emit(runtime.stop(a.run_id, root))
        return 0
    if a.action == "cleanup":
        emit(runtime.cleanup_all())
        return 0
    series = _series_for(a)
    if not series:
        print("Cannot determine Odoo series; pass --series", file=sys.stderr)
        return 2
    addons = _csv(a.addons) or _default_addons(root)
    modules = _csv(a.modules)
    if not modules:
        print("--modules is required", file=sys.stderr)
        return 2
    if a.action == "test":
        res = runtime.test(addons, modules, series, image=a.image, enterprise=a.enterprise, upgrade=not a.no_upgrade,
                           test_tags=a.test_tags, keep=a.keep, project_root=root)
        emit(res)
        return 0 if res["status"] in ("passed",) else 1
    res = runtime.serve(addons, modules, series, image=a.image, enterprise=a.enterprise, port=a.port, project_root=root)
    emit(res)
    return 0 if res.get("status") == "running" else 1


def _default_addons(root: Path) -> list[str]:
    from .odoo.inventory import find_modules, classify_module_location
    return sorted({str(m.parent) for m in find_modules(root) if classify_module_location(m, root) == "custom"})


def cmd_db(a):
    from .odoo import db
    from .config import load_config
    cfg = load_config(_root(a))
    pats = cfg.get("production_patterns", [])
    if a.action == "overview":
        res = db.overview(a.dsn, pats, a.allow_production_readonly)
    else:
        res = db.model_report(a.model, a.dsn, pats, a.allow_production_readonly)
    emit(res)
    return 3 if res.get("refused") else 0


def cmd_classify(a):
    from .planning.classify import classify
    emit(classify(a.request, _root(a)))
    return 0


def cmd_estimate(a):
    from .planning.estimate import estimate
    data = json.loads(Path(a.input).read_text()) if a.input else json.loads(sys.stdin.read())
    emit(estimate(data, _root(a)))
    return 0


def cmd_workflow(a):
    from .workflow import engine
    root = _root(a)
    act = a.action
    if act == "list":
        emit(engine.list_workflows())
    elif act == "validate":
        res = engine.validate_all() if not a.name else engine.validate_definition(engine.load_definition(a.name))
        emit(res)
        return 0 if (res.get("valid") if isinstance(res, dict) and "valid" in res else all(r["valid"] for r in res.values())) else 1
    elif act == "start":
        inputs = dict(kv.split("=", 1) for kv in (a.input or []))
        emit(engine.start(a.name, inputs, root, ticket=a.ticket))
    elif act == "next":
        emit(engine.next_steps(a.execution, root))
    elif act == "complete":
        out = json.loads(Path(a.output).read_text()) if a.output else {}
        emit(engine.complete(a.execution, a.step, a.status, out, root, note=a.note))
    elif act == "approve":
        emit(engine.approve(a.execution, a.step, a.by, root, decision=a.decision, note=a.note))
    elif act == "status":
        emit(engine.status(a.execution, root))
    elif act == "cancel":
        emit(engine.cancel(a.execution, root, reason=a.note))
    elif act == "set":
        emit(engine.set_context(a.execution, dict(kv.split("=", 1) for kv in (a.input or [])), root))
    elif act == "executions":
        emit(engine.list_executions(root))
    return 0


def cmd_mcp(a):
    from .mcp import registry
    root = _root(a)
    if a.action == "servers":
        emit(registry.configured_servers(root))
    elif a.action == "probe":
        emit(registry.probe_all(root, timeout=a.timeout, names=_csv(a.names)))
    elif a.action == "register":
        tools = json.loads(Path(a.tools).read_text()) if a.tools else json.loads(sys.stdin.read())
        emit(registry.register_tools(tools, root, server=a.server))
    elif a.action == "registry":
        emit(registry.load_registry(root))
    elif a.action == "resolve":
        res = registry.resolve(a.capability, root, provider=a.provider)
        emit(res)
        return 0 if res.get("tools") else 1
    elif a.action == "log":
        emit(registry.recent_calls(root, limit=a.limit))
    return 0


def cmd_events(a):
    from .integrations import events
    root = _root(a)
    if a.action == "serve":
        events.serve(root, host=a.host, port=a.port)
    elif a.action == "simulate":
        body = Path(a.payload).read_bytes()
        emit(events.simulate(a.source, body, root, headers=dict(kv.split("=", 1) for kv in (a.header or []))))
    elif a.action == "routes":
        emit(events.load_routes(root))
    elif a.action == "executions":
        emit(events.list_records(root))
    return 0


def cmd_report(a):
    from .reporting import render
    res = render.render(Path(a.input), formats=_csv(a.formats) or ["html", "pdf"], out_dir=Path(a.out) if a.out else None,
                        title=a.title, project_root=_root(a))
    emit(res)
    return 0 if all(r.get("ok") for r in res["outputs"]) else 1


def cmd_evidence(a):
    from .reporting import evidence
    root = _root(a)
    if a.action == "add":
        emit(evidence.add(a.execution, a.kind, a.level, a.path, root, summary=a.summary, status=a.status, command=a.command))
    elif a.action == "manifest":
        emit(evidence.manifest(a.execution, root))
    elif a.action == "verify":
        res = evidence.verify(a.execution, root)
        emit(res)
        return 0 if res["ok"] else 1
    return 0


def cmd_schema(a):
    from .schemas import validate_file
    res = validate_file(a.schema, Path(a.file))
    emit(res)
    return 0 if res["valid"] else 1


def cmd_config(a):
    from .config import load_config
    emit(load_config(_root(a)))
    return 0


def cmd_bootstrap(a):
    from .hooks.session_start import bootstrap
    emit(bootstrap(_root(a)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="odoo-master", description=__doc__)
    p.add_argument("--root", help="project root (default: CLAUDE_PROJECT_DIR or nearest git root)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("analyze", help="full project analysis -> .odoo-master/*")
    s.add_argument("--brief", action="store_true"); s.add_argument("--no-write", action="store_true")
    s.add_argument("--include-core", action="store_true"); s.set_defaults(fn=cmd_analyze)

    s = sub.add_parser("detect-version"); s.add_argument("--brief", action="store_true"); s.set_defaults(fn=cmd_detect_version)
    s = sub.add_parser("inventory"); s.add_argument("--summary", action="store_true"); s.add_argument("--include-core", action="store_true")
    s.set_defaults(fn=cmd_inventory)

    s = sub.add_parser("validate", help="static Odoo validation")
    s.add_argument("--series"); s.add_argument("--modules"); s.add_argument("--files"); s.add_argument("--brief", action="store_true")
    s.add_argument("--no-js", action="store_true"); s.add_argument("--min-severity", choices=["info", "warning", "error"])
    s.set_defaults(fn=cmd_validate)

    s = sub.add_parser("migration"); s.add_argument("action", choices=["scan", "plan"])
    s.add_argument("--from", dest="source", required=True); s.add_argument("--to", dest="target", required=True)
    s.add_argument("--modules"); s.set_defaults(fn=cmd_migration)

    s = sub.add_parser("logs"); s.add_argument("action", choices=["summarize"]); s.add_argument("file"); s.set_defaults(fn=cmd_logs)

    s = sub.add_parser("runtime", help="ephemeral Odoo in Docker")
    s.add_argument("action", choices=["check", "test", "serve", "stop", "status", "cleanup"])
    s.add_argument("--series"); s.add_argument("--addons"); s.add_argument("--modules"); s.add_argument("--image")
    s.add_argument("--enterprise"); s.add_argument("--no-upgrade", action="store_true"); s.add_argument("--test-tags")
    s.add_argument("--keep", action="store_true"); s.add_argument("--port", type=int, default=8069); s.add_argument("--run-id")
    s.set_defaults(fn=cmd_runtime)

    s = sub.add_parser("db", help="read-only PostgreSQL inspection")
    s.add_argument("action", choices=["overview", "model"]); s.add_argument("--dsn"); s.add_argument("--model")
    s.add_argument("--allow-production-readonly", action="store_true"); s.set_defaults(fn=cmd_db)

    s = sub.add_parser("classify"); s.add_argument("request"); s.set_defaults(fn=cmd_classify)
    s = sub.add_parser("estimate"); s.add_argument("--input"); s.set_defaults(fn=cmd_estimate)

    s = sub.add_parser("workflow")
    s.add_argument("action", choices=["list", "validate", "start", "next", "complete", "approve", "status", "cancel", "set", "executions"])
    s.add_argument("name", nargs="?"); s.add_argument("--execution", "-e"); s.add_argument("--step"); s.add_argument("--status", default="DONE")
    s.add_argument("--output"); s.add_argument("--input", "-i", action="append"); s.add_argument("--ticket"); s.add_argument("--by")
    s.add_argument("--decision", default="approved", choices=["approved", "rejected"]); s.add_argument("--note")
    s.set_defaults(fn=cmd_workflow)

    s = sub.add_parser("mcp", help="MCP capability discovery")
    s.add_argument("action", choices=["servers", "probe", "register", "registry", "resolve", "log"])
    s.add_argument("capability", nargs="?"); s.add_argument("--tools"); s.add_argument("--server"); s.add_argument("--provider")
    s.add_argument("--names"); s.add_argument("--timeout", type=int, default=20); s.add_argument("--limit", type=int, default=50)
    s.set_defaults(fn=cmd_mcp)

    s = sub.add_parser("events", help="webhook event ingestion")
    s.add_argument("action", choices=["serve", "simulate", "routes", "executions"])
    s.add_argument("--source"); s.add_argument("--payload"); s.add_argument("--header", action="append")
    s.add_argument("--host", default="127.0.0.1"); s.add_argument("--port", type=int, default=8787); s.set_defaults(fn=cmd_events)

    s = sub.add_parser("report", help="render Markdown to HTML/PDF")
    s.add_argument("input"); s.add_argument("--formats"); s.add_argument("--out"); s.add_argument("--title"); s.set_defaults(fn=cmd_report)

    s = sub.add_parser("evidence")
    s.add_argument("action", choices=["add", "manifest", "verify"]); s.add_argument("--execution", "-e", default="adhoc")
    s.add_argument("--kind"); s.add_argument("--level"); s.add_argument("--path"); s.add_argument("--summary"); s.add_argument("--status")
    s.add_argument("--command"); s.set_defaults(fn=cmd_evidence)

    s = sub.add_parser("schema"); s.add_argument("schema"); s.add_argument("file"); s.set_defaults(fn=cmd_schema)
    s = sub.add_parser("config"); s.set_defaults(fn=cmd_config)
    s = sub.add_parser("bootstrap"); s.set_defaults(fn=cmd_bootstrap)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args) or 0
    except (ValueError, FileNotFoundError, KeyError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
