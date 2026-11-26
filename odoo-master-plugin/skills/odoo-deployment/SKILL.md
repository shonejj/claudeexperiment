---
name: odoo-deployment
description: "Preparing Odoo deployments: Docker/compose and official image conventions, odoo.conf review (workers, limits, proxy_mode, gevent port, dbfilter, list_db, admin_passwd), reverse proxy with websocket routing, Odoo.sh, module upgrade lists, backups and rollback runbooks. Use for deploy preparation and environment setup."
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

# Odoo deployment

- Official image `odoo:<series>`: env `HOST`, `PORT`, `USER`, `PASSWORD` (or `PASSWORD_FILE`); volumes `/var/lib/odoo` (filestore, must match `data_dir`), `/etc/odoo/odoo.conf`, `/mnt/extra-addons`; CLI args after the command (`odoo --db-filter=...`).
- Production config checklist: `workers` (rule of thumb (#CPU*2)+1), `max_cron_threads`, `limit_memory_soft/hard`, `limit_time_cpu/real`, `proxy_mode = True` behind a proxy, `/websocket` routed to `gevent_port` (8072), `dbfilter` + `list_db = False`, strong `admin_passwd`, non-superuser PostgreSQL role.
- Upgrade list: changed modules + reverse dependencies from `.odoo-master/module-dependency-map.json`; never `-u all` on production without approval.
- Rehearse: `odoo-master runtime test --modules <list>` and/or a staging copy; attach `odoo-master logs summarize`.
- Backups: `pg_dump -Fc` + filestore tarball (or `odoo-bin db dump <db> <path>` 17+); record sha256 in evidence.
- Odoo.sh: branch stages (dev/staging/production), staging from a neutralized production copy, requirements.txt auto-install, upgrades via the platform.
- Output a runbook (templates/reports/runbook.md): pre-checks, commands in order, verification, rollback. Humans execute production steps.
