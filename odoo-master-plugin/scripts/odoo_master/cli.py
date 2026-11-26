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
    from .odoo.version import detect, brief, confirm
    if a.confirm:
        emit(confirm(_root(a), a.confirm))
        return 0
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
    from .config import load_config
    rcfg = load_config(root).get("runtime") or {}
    a.enterprise = a.enterprise or rcfg.get("enterprise_path") or None
    a.image = a.image or rcfg.get("image") or None
    pg_image = rcfg.get("postgres_image") or "postgres:16"
    if a.action == "test":
        res = runtime.test(addons, modules, series, image=a.image, enterprise=a.enterprise, pg_image=pg_image, upgrade=not a.no_upgrade,
                           test_tags=a.test_tags, keep=a.keep, project_root=root)
        emit(res)
        return 0 if res["status"] in ("passed",) else 1
    res = runtime.serve(addons, modules, series, image=a.image, enterprise=a.enterprise, pg_image=pg_image, port=a.port, project_root=root)
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
    from .planning.estimate import estimate, to_markdown
    data = json.loads(Path(a.input).read_text()) if a.input else json.loads(sys.stdin.read())
    est = estimate(data, _root(a))
    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.with_suffix(".json").write_text(json.dumps(est, indent=2))
        out.with_suffix(".md").write_text(to_markdown(est))
        est["written"] = [str(out.with_suffix(".json")), str(out.with_suffix(".md"))]
    emit(est)
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


def cmd_scaffold(a):
    from .odoo.scaffold import write
    series = _series_for(a)
    if not series:
        print("Cannot determine Odoo series; pass --series", file=sys.stderr)
        return 2
    target = Path(a.path) if a.path else (Path(_default_addons(_root(a))[0]) if _default_addons(_root(a)) else _root(a))
    res = write(target, a.name, series, model=a.model, depends=_csv(a.depends), title=a.title, license=a.license,
                author=a.author, with_tests=not a.no_tests)
    if not a.no_validate:
        from .odoo.validate import validate
        v = validate(_root(a) if Path(res["path"]).resolve().is_relative_to(_root(a)) else Path(res["path"]).parent,
                     series=series, modules=[a.name], with_js=False)
        res["validation"] = {"passed": v["passed"], "counts": v["counts"],
                             "errors": [f for f in v["findings"] if f["severity"] == "error"]}
    emit(res)
    return 0 if res.get("validation", {}).get("passed", True) else 1


def cmd_source(a):
    from .odoo import source
    series = _series_for(a)
    if a.action == "grep":
        emit(source.grep(a.pattern, series, module=a.module, image=a.image, max_results=a.limit))
    elif a.action == "show":
        res = source.show(a.pattern, series, start=a.start, end=a.end, image=a.image)
        print(res["content"]) if a.plain else emit(res)
    elif a.action == "upgrade-code":
        if not a.source or not a.target:
            print("--from and --to are required", file=sys.stderr)
            return 2
        addons = a.pattern or (_default_addons(_root(a)) or [str(_root(a))])[0]
        if not a.apply:
            res = source.upgrade_code(addons, a.source, a.target, dry_run=True, image=a.image, script=a.script)
        else:
            from .repository import git_state
            g = git_state(_root(a))
            if g.get("is_git") and g.get("dirty") and not a.force:
                print("refusing to rewrite files in a dirty working tree; commit/stash first or pass --force", file=sys.stderr)
                return 3
            res = source.upgrade_code(addons, a.source, a.target, dry_run=False, image=a.image, script=a.script)
        emit(res)
        return 0 if res["exit_code"] == 0 else 1
    return 0


def cmd_lookup(a):
    from .odoo import source
    series = _series_for(a) or "19.0"
    emit(source.lookup_model(a.name, series) if a.kind == "model" else source.lookup_module(a.name, series))
    return 0


def cmd_doctor(a):
    from .ops import doctor
    res = doctor(_root(a), check_images=not a.quick)
    if a.brief:
        print(f"overall: {res['overall']}")
        for c in res["checks"]:
            print(f"  {c['status']:5} {c['check']:22} {c['detail']}" + (f"  → {c['fix']}" if c["status"] != "ok" and c["fix"] else ""))
    else:
        emit(res)
    return 1 if a.strict and res["overall"] != "ok" else 0


def cmd_init(a):
    from .ops import init
    emit(init(_root(a), with_events=a.events, with_settings=a.settings, force=a.force))
    return 0


def cmd_status(a):
    from .ops import status
    res = status(_root(a))
    if a.brief:
        ex = res["executions"]
        print(f"Odoo {res['odoo_version'] or 'unknown'} ({res['confidence']}) | modules={res['modules']} | active executions={len(ex['active'])} "
              f"| waiting approval={len(ex['waiting_approval'])} | mcp servers={len(res['mcp'])} | runtime instances={len(res['runtime_instances'])}")
        for w in ex["waiting_approval"]:
            print(f"  APPROVAL: {w['execution']} step {w['step']} ticket {w['ticket']}")
        for e in ex["active"]:
            print(f"  ACTIVE: {e['id']} {e['workflow']} [{e['status']}] ticket {e['ticket']}")
    else:
        emit(res)
    return 0


def cmd_watch(a):
    from .ops import watch
    watch(_root(a), interval=a.interval, once=a.once)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="odoo-master", description=__doc__)
    p.add_argument("--root", help="project root (default: CLAUDE_PROJECT_DIR or nearest git root)")
    p.add_argument("--soft", action="store_true",
                   help="never fail: always exit 0 and print 'unavailable: <reason>' on errors (for skill !-injection)")
    p.add_argument("--max-lines", type=int, help="truncate output to N lines (replaces piping to head)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("analyze", help="full project analysis -> .odoo-master/*")
    s.add_argument("--brief", action="store_true"); s.add_argument("--no-write", action="store_true")
    s.add_argument("--include-core", action="store_true"); s.set_defaults(fn=cmd_analyze)

    s = sub.add_parser("detect-version"); s.add_argument("--brief", action="store_true")
    s.add_argument("--confirm", metavar="SERIES", help="record the target series confirmed by the user (resolves conflicts)")
    s.set_defaults(fn=cmd_detect_version)
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
    s = sub.add_parser("estimate"); s.add_argument("--input"); s.add_argument("--out", help="write <out>.json and <out>.md")
    s.set_defaults(fn=cmd_estimate)

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

    s = sub.add_parser("scaffold", help="version-correct module skeleton (16.0-20.0)")
    s.add_argument("name"); s.add_argument("--series"); s.add_argument("--path", help="addons directory (default: first custom addons path)")
    s.add_argument("--model"); s.add_argument("--depends", default="base"); s.add_argument("--title"); s.add_argument("--license", default="LGPL-3")
    s.add_argument("--author"); s.add_argument("--no-tests", action="store_true"); s.add_argument("--no-validate", action="store_true")
    s.set_defaults(fn=cmd_scaffold)

    s = sub.add_parser("source", help="read standard Odoo source in the official image; run upgrade_code")
    s.add_argument("action", choices=["grep", "show", "upgrade-code"]); s.add_argument("pattern", nargs="?", help="regex (grep), path (show) or addons dir (upgrade-code)")
    s.add_argument("--series"); s.add_argument("--module"); s.add_argument("--image"); s.add_argument("--limit", type=int, default=200)
    s.add_argument("--start", type=int, default=1); s.add_argument("--end", type=int); s.add_argument("--plain", action="store_true")
    s.add_argument("--from", dest="source"); s.add_argument("--to", dest="target"); s.add_argument("--script")
    s.add_argument("--apply", action="store_true", help="rewrite files (default is --dry-run)"); s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_source)

    s = sub.add_parser("lookup", help="standard model/module knowledge (offline)")
    s.add_argument("kind", choices=["model", "module"]); s.add_argument("name"); s.add_argument("--series"); s.set_defaults(fn=cmd_lookup)

    s = sub.add_parser("doctor", help="check the environment and optional tools")
    s.add_argument("--brief", action="store_true"); s.add_argument("--quick", action="store_true"); s.add_argument("--strict", action="store_true")
    s.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("init", help="create .odoo-master/config.yaml (+ event routes, + recommended permissions)")
    s.add_argument("--events", action="store_true"); s.add_argument("--settings", action="store_true", help="merge recommended permissions into .claude/settings.json (backup first)")
    s.add_argument("--force", action="store_true"); s.set_defaults(fn=cmd_init)

    s = sub.add_parser("status", help="dashboard: version, executions, approvals, MCP, runtime instances")
    s.add_argument("--brief", action="store_true"); s.set_defaults(fn=cmd_status)

    s = sub.add_parser("watch", help="print one line per approval request / finished execution / new event (for monitors)")
    s.add_argument("--interval", type=float, default=15.0); s.add_argument("--once", action="store_true"); s.set_defaults(fn=cmd_watch)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if not (args.soft or args.max_lines):
        try:
            return args.fn(args) or 0
        except (ValueError, KeyError, OSError) as exc:   # OSError covers FileNotFoundError and read-only filesystems
            print(json.dumps({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr)
            return 2
    import contextlib
    import io
    buf = io.StringIO()
    rc = 0
    try:
        with contextlib.redirect_stdout(buf):
            rc = args.fn(args) or 0
    except Exception as exc:  # noqa: BLE001 - soft mode reports instead of failing
        buf.write(f"unavailable: {type(exc).__name__}: {exc}\n")
        rc = 2
    text = buf.getvalue()
    if args.max_lines:
        lines = text.splitlines()
        if len(lines) > args.max_lines:
            text = "\n".join(lines[: args.max_lines]) + f"\n... ({len(lines) - args.max_lines} more lines)\n"
    sys.stdout.write(text)
    return 0 if args.soft else rc


if __name__ == "__main__":
    sys.exit(main())
