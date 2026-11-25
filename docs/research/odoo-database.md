# Odoo database (research notes)

Sources: `content/developer/reference/backend/orm.rst` (SQL execution, field storage),
`administration/on_premise/deploy.rst` (PostgreSQL and the database manager),
`content/developer/reference/cli.rst` (`db` subcommands), and the source in images 17–20.

## How the ORM maps to PostgreSQL
| ORM | Schema |
|---|---|
| `_name = 'sale.order'` | table `sale_order` (dots → underscores); `_table` overrides it |
| stored field | column; `Many2one` → `integer` FK with `ON DELETE` from `ondelete=` (`set null` default, `restrict`, `cascade`) |
| `One2many` | no column (inverse of a Many2one) |
| `Many2many` | relation table `<model1>_<model2>_rel` (sorted names) or the explicit `relation=` |
| non-stored compute / related | no column |
| `translate=True` | `jsonb` column with one key per language (16+) |
| `company_dependent=True` | `jsonb` column keyed by company id (18+; `ir.property` before) |
| `index=True` | btree index `<table>__<column>_index` |
| `_sql_constraints` (≤18) / `models.Constraint` (19+) | named table constraint `<table>_<name>` |
| `Binary(attachment=True)` (default) | row in `ir_attachment` + file in the filestore |

Automatic columns: `id`, `create_uid`, `create_date`, `write_uid`, `write_date`.
Metadata tables: `ir_model`, `ir_model_fields`, `ir_model_data` (external IDs:
`module`, `name`, `model`, `res_id`, `noupdate`), `ir_module_module` (state, latest_version),
`ir_module_module_dependency`, `ir_ui_view`, `ir_attachment`.

## What changes the schema
- Installing or upgrading a module (`-i`/`-u`): the ORM creates tables, adds columns and alters
  types where it can. **The ORM never drops columns or tables of removed fields**: old columns stay
  until an upgrade script removes them (`util.remove_field`).
- Renaming a field in Python creates a *new* empty column. Data is lost unless a `pre-` migration
  renames the column (`util.rename_field`).
- Changing a stored field's type can fail or drop data; it needs a migration script.
- XML/CSV data: loaded on install and upgrade. `noupdate="1"` records are created once and not
  overwritten afterwards.

## Inspection queries (read-only, used by `inspect_db.py`)
- `SELECT version()` / `SHOW server_version`
- installed modules: `SELECT name, state, latest_version FROM ir_module_module WHERE state='installed'`
- model ↔ table: `ir_model` + `information_schema.columns`
- missing ACLs: models in `ir_model` with no row in `ir_model_access` (≤19) or `ir_access` (20)
- orphan columns: columns with no matching `ir_model_fields` row (left behind after a field was removed)
- indexes: `pg_indexes`; table sizes: `pg_total_relation_size`
- slow queries: `pg_stat_statements` if the extension is installed
- locks: `pg_locks` joined to `pg_stat_activity`

All of these run inside a `READ ONLY` transaction (`SET TRANSACTION READ ONLY`). The script refuses
to connect if the database name or host matches the production patterns in
`policies/database-safety.yaml`, unless `--allow-production-readonly` is given explicitly.

## Backups and copies
- `odoo-bin db dump <db> <path> [--format zip|dump] [--no-filestore]` (17+), or the database manager
  (`/web/database/manager`, protected by `admin_passwd`, disabled with `list_db = False`).
- `pg_dump -Fc` plus a copy of the filestore directory. **Both** are needed for a restore.
- `odoo-bin neutralize -d <db>` (16+) disables outgoing mail, crons and payment providers on a copy.
  Always neutralize a production copy before testing on it.
- `odoo-bin db duplicate <src> <dst> [--neutralize]` (17+) copies the database and its filestore.

## Safety classes (enforced by `policies/database-safety.yaml` + `guard.py`)
| Class | Examples | Default |
|---|---|---|
| read | SELECT, EXPLAIN (without ANALYZE on writes) | allowed on dev/test; on prod only with explicit flag |
| write-data | UPDATE/INSERT/DELETE with WHERE | needs approval |
| bulk/destructive | DELETE without WHERE, TRUNCATE, DROP, ALTER … DROP, `dropdb`, `db drop` | blocked unless approved |
| schema | ALTER TABLE/CREATE INDEX on prod | approval + backup evidence |
