---
name: odoo-performance
description: "Diagnosing and fixing Odoo performance: N+1 ORM patterns, missing indexes, heavy stored computes, slow views and reports, query counting, profiling, PostgreSQL statistics, worker sizing. Use for slowness, timeouts or scaling questions."
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

# Odoo performance

1. **Baseline** a reproducible scenario: a test with `with self.assertQueryCount(N):`, or a runtime with `--log-sql`/`--log-handler=odoo.sql_db:DEBUG` on a test db, or the profiler (`from odoo.tools.profiler import Profiler`).
2. **Typical culprits**
   - search/browse/read inside loops → batch (`search_fetch`, `read_group`/`_read_group`, `mapped`, prefetch-friendly recordsets).
   - stored compute with wide `@api.depends` on hot fields → narrow deps, or non-stored + `compute_sql` (SaaS 19.1+/20) where grouping is needed.
   - missing index on searched/grouped/ordered columns → `index=True`, `index='trigram'` for ilike, `models.Index` (19+).
   - `sudo()` + broad searches in controllers; huge `One2many` in form views (use `limit`/separate action).
   - cron jobs processing everything at once → batches with commits (18.3+ cron progress API, `_commit_progress`).
3. **Database**: `odoo-master db overview` (largest tables, long-running, locks); `pg_stat_statements` if installed.
4. **Server**: workers `(CPU*2)+1`, memory limits, gevent worker for websocket (docs/research/odoo-deployment.md).
5. **Verify** with the same scenario; report before/after numbers.
