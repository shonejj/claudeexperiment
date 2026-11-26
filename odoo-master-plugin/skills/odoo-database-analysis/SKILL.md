---
name: odoo-database-analysis
description: "Read-only PostgreSQL analysis of Odoo databases: installed modules, schema vs ORM drift, constraints, indexes, table sizes, locks, slow queries, data integrity checks, and safe remediation planning (backup, validation, rollback). Use for database investigations, migration data impact and performance at the SQL level."
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

# Odoo database analysis

## Safety first
- Only authorised databases. Connection via libpq environment (`PGHOST`, `PGPORT`, `PGUSER`, `PGDATABASE`, password in `PGPASSWORD` or `~/.pgpass`) or `--dsn` — never echo the password.
- Production-looking targets (config `production_patterns`) are refused unless the user approved read-only access (`--allow-production-readonly`). Writes are never executed by agents.
- Prefer a neutralized copy: `odoo-bin db duplicate <src> <copy> --neutralize` (17+) or restore a dump + `odoo-bin neutralize`.

## Commands
- `odoo-master db overview` — server version, db size, Odoo base version, installed modules, pending module states, largest tables, long-running queries, waiting locks, `pg_stat_statements` availability, models without ACL.
- `odoo-master db model --model sale.order` — columns, indexes, constraints, row count, ORM fields without column, columns without ORM field (left-overs from removed fields), external ids by module.
- Ad-hoc read-only SQL: wrap in `BEGIN READ ONLY; ... ; ROLLBACK;`.

## Interpreting results
| Finding | Meaning | Remediation |
|---|---|---|
| column without ORM field | field removed/renamed in code | upgrade script `util.remove_field` / rename in `pre-` |
| ORM stored field without column | module not upgraded (`-u`) | upgrade on a copy first |
| module state `to upgrade` | interrupted upgrade | investigate log, rerun on copy |
| unique rule not in `pg_constraint` on 19+ | `_sql_constraints` ignored | `models.Constraint` + data dedupe script |
| seq scans on big table | missing index | `index=True` / `models.Index` (19+) |

Every recommendation: ORM/upgrade-script path, backup step, validation query, rollback.
