# Database standards

- Agents run read-only queries only (`BEGIN READ ONLY`), on authorised, preferably neutralized copies.
- Schema changes go through the ORM (fields, `models.Constraint`, `models.Index`) and upgrade scripts — not
  manual DDL — so every environment converges on module upgrade.
- Data changes on existing databases go in `migrations/<version>/pre-|post-|end-*.py` with logging of affected
  row counts; large updates in batches.
- Before any migration: backup (pg_dump -Fc + filestore) with sha256 recorded, validation queries defined,
  rollback written.
- Destructive operations (DROP, TRUNCATE, DELETE without WHERE, dropping columns with data, `db drop`,
  `neutralize` on the wrong database) require explicit human approval and are blocked by the guard hook.
- Never point tests at production. Test databases are prefixed `om_test_` and disposable.
