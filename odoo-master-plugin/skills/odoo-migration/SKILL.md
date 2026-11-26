---
name: odoo-migration
description: "Migrating custom Odoo modules and their data between major versions (16, 17, 18, 19, 20): migration scan, hop-by-hop porting with odoo-bin upgrade_code, upgrade scripts (pre/post/end) with upgrade-util, data validation, neutralized test copies, risk assessment and rollback. Use for any version upgrade or porting task."
---

# Odoo migration

## 1. Scope
`odoo-master migration plan --from <src> --to <dst> [--modules a,b]` → hops, rule findings per module (file:line, since-version, source citation), blockers vs changes, plan skeleton with validation and rollback.

## 2. Two different migrations — say which one
- **Standard modules + database** across majors: upgrade.odoo.com / Odoo.sh upgrade (Enterprise & paid Community), or OCA OpenUpgrade for Community. The plugin does not replace these.
- **Custom code + custom data**: this skill.

## 3. Port per hop (never skip)
```
git switch -c migrate/<hop>
docker run --rm -v $PWD/addons:/mnt/extra-addons odoo:<hop> odoo upgrade_code --addons-path /mnt/extra-addons --from <prev> --to <hop> --dry-run
# review list → run without --dry-run on the branch → review the diff file by file
odoo-master migration scan --from <prev> --to <hop>      # remaining findings
odoo-master validate --series <hop> --brief
```
(`upgrade_code` ships in 18.0+ images; for 16→17 apply the rule list manually.)

## 4. Data: upgrade scripts
```
<module>/migrations/18.0.2.0.0/pre-10-rename.py
<module>/migrations/18.0.2.0.0/post-20-fill.py
```
```python
from odoo.upgrade import util          # needs upgrade-util on --upgrade-path or pip

def migrate(cr, version):              # version = installed version (None on fresh install)
    util.rename_field(cr, "sale.order", "x_old", "x_new")
```
- Scripts run only on `-u` when `installed < dir version <= new manifest version` → bump the manifest.
- `pre-` before module load (renames, column prep), `post-` after (ORM data fixes), `end-` after all modules.
- 19.0: re-create unique rules as `models.Constraint` and dedupe data first (otherwise constraint creation fails).
- 20.0: convert `ir.model.access.csv` + `ir.rule` into `ir.access.csv` (`19.4-00-ir-access` upgrade_code script).

## 5. Verify (levels)
static scan 0 blockers → install test on target (`odoo-master runtime test --series <hop>`) → upgrade test on a **neutralized** copy already upgraded for standard modules → row counts/spot checks (validation queries) → log summary clean.

## 6. Risk & rollback
Backups (pg_dump -Fc + filestore) with sha256 in evidence, rollback = restore + previous image/tag. Production upgrade is `always_human`.
