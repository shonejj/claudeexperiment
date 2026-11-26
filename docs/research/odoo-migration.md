# Odoo migration (research notes)

Sources: `content/developer/reference/upgrades/upgrade_scripts.rst`, `upgrade_utils.rst`,
`content/administration/upgrade.rst`, `cli.rst` (`upgrade_code`, 19.0), https://github.com/odoo/upgrade-util
(README), `odoo/upgrade_code/*` in the 18/19/20 images, OpenUpgrade (https://github.com/OCA/OpenUpgrade,
community alternative, referenced from the Docker Hub page).

## Two different migrations
1. **Database upgrade (standard modules)** from major version N to M. Odoo SA handles this through
   https://upgrade.odoo.com (Enterprise, or Community via the paid service) or Odoo.sh. Community
   self-hosters can use OCA OpenUpgrade. Process (`administration/upgrade.rst`): request a test
   upgrade → test the upgraded database thoroughly → request the production upgrade.
2. **Custom module migration**: porting *your* code to the new API, plus writing upgrade scripts
   for *your* data. This is the plugin's job.

## Upgrade scripts (custom data)
- Location: `<module>/migrations/<full_version>/` or `<module>/upgrades/<full_version>/` (preferred
  name from 13). `full_version` = Odoo series + module version, e.g. `18.0.2.0.0`.
- Files: `pre-*.py` (before the module loads: rename columns/models), `post-*.py` (after the module
  and its dependencies are updated: data fixes using the ORM), `end-*.py` (after all modules
  updated). Lexical order within a phase.
- Signature: `def migrate(cr, version):`. `version` is the *installed* version (None on new install).
- Scripts run only on update (`-u`), when the directory version is greater than the installed
  version and less than or equal to the new version. So the manifest version **must** be bumped.
- `from odoo.upgrade import util` (install upgrade-util and use `--upgrade-path=<upgrade-util>/src`).
  Helpers include `util.env(cr)`, `util.rename_field`, `util.rename_model`, `util.remove_field`,
  `util.remove_model`, `util.rename_xmlid`, `util.remove_view`, `util.column_exists`,
  `util.create_column`, `util.merge_module`, `util.update_record_from_xml`.

## Code porting
- Run `odoo-bin upgrade_code --addons-path <custom> --from <src> --to <dst> --dry-run` (18+), then
  without `--dry-run` on a branch, then review the diff. Scripts include tree→list, sql-constraint,
  route-jsonrpc, ir-access (20), owl3.
- Apply the manual checklist in `odoo-master-plugin/knowledge/migration-checklists.yaml`. It is
  generated from the compatibility table in `odoo-version-compatibility.md` and consumed by
  `migration_scan.py`, which greps the module for every pattern that has to change between the
  source and target versions.
- Multi-version jumps go one major at a time (16→17→18→19), because each upgrade_code script and
  each standard module's own upgrade scripts assume the previous major.

## Validation plan (what "migration verified" means)
1. Static: `migration_scan.py` reports 0 remaining blockers for the target version.
2. Install test: fresh database on the target version, `-i <module> --test-tags /<module>`.
3. Upgrade test: restore a **neutralized copy** of real data that has already been upgraded for
   standard modules, then `-u <module>`, then check row counts and spot-check key records
   (`validation_queries` in the migration plan).
4. Log check: `odoo_log_summary.py` shows no `ERROR`/`CRITICAL` and no tracebacks.
5. Rollback: the restore point is a `pg_dump` plus the filestore taken before the upgrade. The plan
   records its path and checksum.

## Risks to flag in every plan
Field renames without `pre-` scripts (silent data loss), removed `_sql_constraints` in 19 (unique
rules silently not enforced), `ir.model.access` → `ir.access` in 20 (CSV must be rewritten),
`groups_id` → `group_ids` in 19 (XML and Python), `attrs` (fails at load in 17+), OWL 2 → 3 (20),
`name_get` overrides that no longer run, `type='json'` routes, and Enterprise-only dependencies.
