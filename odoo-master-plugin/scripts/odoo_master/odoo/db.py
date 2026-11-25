"""Read-only PostgreSQL inspection of an Odoo database via the `psql` client.

Safety:
  * every query runs inside `BEGIN READ ONLY` ... `ROLLBACK` (PostgreSQL rejects writes);
  * connection parameters come from the standard libpq environment (PGHOST, PGPORT, PGUSER,
    PGPASSWORD / ~/.pgpass, PGDATABASE) or an explicit DSN, and are never printed;
  * databases or hosts matching the configured production patterns are refused unless
    allow_production_readonly=True is passed explicitly (an approval-gated action).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess

from ..util import redact_text

QUERIES = {
    "server_version": "SHOW server_version",
    "database_size": "SELECT pg_size_pretty(pg_database_size(current_database()))",
    "odoo_series": "SELECT latest_version FROM ir_module_module WHERE name='base'",
    "installed_modules": "SELECT name, latest_version FROM ir_module_module WHERE state='installed' ORDER BY name",
    "modules_to_upgrade": "SELECT name, state FROM ir_module_module WHERE state IN ('to upgrade','to install','to remove') ORDER BY name",
    "largest_tables": ("SELECT relname, pg_size_pretty(pg_total_relation_size(c.oid)), reltuples::bigint "
                       "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND relkind='r' "
                       "ORDER BY pg_total_relation_size(c.oid) DESC LIMIT 20"),
    "long_running": ("SELECT pid, state, now()-query_start AS age, left(query,120) FROM pg_stat_activity "
                     "WHERE datname=current_database() AND state<>'idle' ORDER BY age DESC LIMIT 10"),
    "locks_waiting": "SELECT count(*) FROM pg_locks WHERE NOT granted",
    "pg_stat_statements_available": "SELECT count(*) FROM pg_extension WHERE extname='pg_stat_statements'",
}

MODEL_QUERIES = {
    "columns": ("SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns "
                "WHERE table_name=%(table)s ORDER BY ordinal_position"),
    "indexes": "SELECT indexname, indexdef FROM pg_indexes WHERE tablename=%(table)s",
    "constraints": ("SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid=%(table)s::regclass"),
    "row_count": "SELECT count(*) FROM {table}",
    "orm_fields_without_column": ("SELECT f.name, f.ttype FROM ir_model_fields f WHERE f.model=%(model)s AND f.store "
                                  "AND f.ttype NOT IN ('one2many','many2many') AND NOT EXISTS (SELECT 1 FROM information_schema.columns c "
                                  "WHERE c.table_name=%(table)s AND c.column_name=f.name)"),
    "columns_without_orm_field": ("SELECT c.column_name FROM information_schema.columns c WHERE c.table_name=%(table)s "
                                  "AND c.column_name NOT IN ('id','create_uid','create_date','write_uid','write_date') AND NOT EXISTS "
                                  "(SELECT 1 FROM ir_model_fields f WHERE f.model=%(model)s AND f.name=c.column_name)"),
    "external_ids": "SELECT module, count(*) FROM ir_model_data WHERE model=%(model)s GROUP BY module ORDER BY 2 DESC",
}

ACL_QUERIES = {
    "models_without_acl_legacy": ("SELECT m.model FROM ir_model m WHERE m.transient = false AND NOT EXISTS "
                                  "(SELECT 1 FROM ir_model_access a WHERE a.model_id=m.id) ORDER BY 1 LIMIT 200"),
    "models_without_acl_20": ("SELECT m.model FROM ir_model m WHERE NOT EXISTS (SELECT 1 FROM ir_access a WHERE a.model_id=m.id) "
                              "ORDER BY 1 LIMIT 200"),
}

_IDENT = re.compile(r"^[a-z_][a-z0-9_.]*$")


def _quote(v: str) -> str:
    return "'" + str(v).replace("'", "''") + "'"


def is_production(target: str, patterns: list[str]) -> bool:
    return any(re.search(p, target or "", re.I) for p in patterns)


def _target_desc(dsn: str | None) -> str:
    if dsn:
        return redact_text(dsn)
    return f"{os.environ.get('PGHOST', 'localhost')}/{os.environ.get('PGDATABASE', '')}"


def run_query(sql: str, dsn: str | None = None, timeout: int = 60) -> dict:
    if not shutil.which("psql"):
        return {"ok": False, "error": "psql client not installed"}
    script = f"BEGIN READ ONLY;\n{sql};\nROLLBACK;\n"
    cmd = ["psql", "-X", "-A", "-F", "\t", "-P", "footer=off", "-v", "ON_ERROR_STOP=1", "-q"]
    if dsn:
        cmd.append(dsn)
    r = subprocess.run(cmd, input=script, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        return {"ok": False, "error": redact_text(r.stderr.strip())[:800]}
    lines = [ln for ln in r.stdout.splitlines() if ln and ln not in ("BEGIN", "ROLLBACK")]
    if not lines:
        return {"ok": True, "columns": [], "rows": []}
    header, rows = lines[0].split("\t"), [ln.split("\t") for ln in lines[1:]]
    return {"ok": True, "columns": header, "rows": rows[:500], "truncated": len(rows) > 500}


def overview(dsn: str | None = None, production_patterns: list[str] | None = None, allow_production_readonly: bool = False) -> dict:
    target = _target_desc(dsn)
    if is_production(target, production_patterns or []) and not allow_production_readonly:
        return {"ok": False, "refused": True, "reason": f"target '{target}' matches a production pattern; "
                "read-only inspection of production needs explicit approval (--allow-production-readonly)."}
    out = {"target": target, "level": "database", "results": {}}
    for k, q in QUERIES.items():
        out["results"][k] = run_query(q, dsn)
    series = (out["results"].get("odoo_series", {}).get("rows") or [[None]])[0][0]
    acl_q = ACL_QUERIES["models_without_acl_20"] if series and series.startswith("20.") else ACL_QUERIES["models_without_acl_legacy"]
    out["results"]["models_without_acl"] = run_query(acl_q, dsn)
    out["ok"] = all(r.get("ok") for k, r in out["results"].items() if k in ("server_version",))
    return out


def model_report(model: str, dsn: str | None = None, production_patterns: list[str] | None = None,
                 allow_production_readonly: bool = False) -> dict:
    if not _IDENT.match(model):
        raise ValueError("invalid model name")
    target = _target_desc(dsn)
    if is_production(target, production_patterns or []) and not allow_production_readonly:
        return {"ok": False, "refused": True, "reason": "production target; approval required"}
    table = model.replace(".", "_")
    out = {"model": model, "table": table, "results": {}}
    for k, q in MODEL_QUERIES.items():
        sql = q.format(table=table) if "{table}" in q else q % {"table": _quote(table), "model": _quote(model)}
        out["results"][k] = run_query(sql, dsn)
    return out
