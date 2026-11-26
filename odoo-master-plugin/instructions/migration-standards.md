# Migration standards

- One major version per hop; each hop is its own branch, scan, port, validation and evidence.
- Start with `odoo-master migration plan`; use `odoo-bin upgrade_code --dry-run` where available; review every
  automated rewrite.
- Every stored-field rename/retype/removal has an upgrade script; manifest versions bumped.
- Re-declare constraints for 19.0 (`models.Constraint`) and access for 20.0 (`ir.access`).
- Validation = 0 blocker findings + install test + upgrade test on a neutralized copy + data spot checks + clean
  log summary. Rollback = restore backup + previous release.
- Production upgrades are executed by humans from an approved runbook.
