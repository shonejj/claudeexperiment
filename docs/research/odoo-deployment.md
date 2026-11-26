# Odoo deployment (research notes)

Sources: `content/administration/on_premise/{deploy,source,packages,update}.rst`, `odoo_sh/*`,
`cli.rst`, the Docker Hub page for `odoo` (https://hub.docker.com/_/odoo), and `/etc/odoo/odoo.conf`
in the official images.

## Official Docker image
- Tags in Nov 2026: `20.0`/`20`/`latest`, `19.0`/`19`, `18.0`/`18` (plus dated tags such as
  `19.0-20261123`). 17.0 is still pullable (verified) but no longer listed as supported.
- Environment: `HOST` (default `db`), `PORT` (5432), `USER` (`odoo`), `PASSWORD` (`odoo`),
  `PASSWORD_FILE` for Docker secrets.
- Volumes: `/var/lib/odoo` (data_dir: filestore and sessions; must match `data_dir`), `/etc/odoo`
  (`odoo.conf`), `/mnt/extra-addons` (custom and Enterprise addons).
- Odoo CLI arguments go after `--`, e.g. `docker run … odoo:19.0 -- --db-filter=^mydb$`.
- Image updates stay within one major version. Major upgrades need migration (upgrade.odoo.com or
  OpenUpgrade).
- Default conf in the images: `addons_path = /mnt/extra-addons`, `data_dir = /var/lib/odoo`.

## Production configuration (`deploy.rst`)
- **Workers:** rule of thumb `(#CPU * 2) + 1`; 1 worker ≈ 6 concurrent users; plus cron threads.
  RAM ≈ `workers * (0.8*150MB + 0.2*1GB)`. Sample: `workers = 8`, `max_cron_threads = 1`,
  `limit_memory_soft = 629145600`, `limit_memory_hard = 1677721600`, `limit_time_cpu = 600`,
  `limit_time_real = 1200`, `limit_request = 8192`.
- **Live chat / bus:** with workers > 0, a gevent worker listens on `--gevent-port` (default 8072).
  The reverse proxy must route `/websocket` there with `Upgrade`/`Connection` headers. Odoo must
  run with `proxy_mode = True` behind a proxy.
- **dbfilter / list_db:** set `dbfilter` (e.g. `^%d$` for subdomain-per-db) and `list_db = False`
  once one database is served per host. Change `admin_passwd` from its default (or disable the
  manager).
- **HTTPS:** nginx example in `deploy.rst` (`proxy_read_timeout 720s`, `X-Forwarded-*` headers,
  `proxy_cookie_flags session_id samesite=lax secure`).
- **PostgreSQL:** a dedicated non-superuser role; do not run Odoo as `postgres`. `db_maxconn`
  defaults to 64.
- **wkhtmltopdf** 0.12.6 (patched Qt) for PDF reports.
- **Filestore** lives under `data_dir/filestore/<db>`. It must be backed up together with the
  database.

## Odoo.sh
Git-based: branches are production, staging or development. Custom addons sit at the repository
root (or in submodules). Enterprise is provided by the platform. `requirements.txt` is installed
automatically. Staging builds use a neutralized copy of production. Upgrades go through the
platform's upgrade button, which calls upgrade.odoo.com.

## Deployment checklist used by `deployment-safety.yaml` / `devops-engineer`
1. The target is never production without an approval record.
2. A backup (dump + filestore) exists and is younger than the configured maximum age.
3. Module upgrade list computed from changed modules and their reverse dependencies.
4. `-u` run on staging with `--stop-after-init`, and the log summary is clean.
5. Workers, proxy and websocket configuration checked when the config changes.
6. A rollback command is recorded in the plan.

## Monitoring and logging
`--logfile`, `--log-handler=odoo.sql_db:DEBUG` for SQL debugging (dev only), `--log-level`,
syslog, `/web/health` endpoint (17+) for liveness checks, PostgreSQL `pg_stat_statements` for slow
queries.
