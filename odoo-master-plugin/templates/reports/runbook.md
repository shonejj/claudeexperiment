# Deployment runbook — {{title}}

Environment: {{env}} · Odoo {{series}} · Prepared by odoo-master execution {{execution}} · **Executed by a human operator**

## Pre-checks
- [ ] Backup taken: `pg_dump -Fc {{db}} > {{file}}` + filestore archive; sha256 recorded
- [ ] Staging rehearsal clean (log summary attached)
- [ ] Approval recorded: {{who/when}}

## Steps
1. {{maintenance window / stop workers}}
2. `odoo -c /etc/odoo/odoo.conf -d {{db}} -u {{modules}} --stop-after-init`
3. {{restart service}}

## Verification
- {{checks}}

## Rollback
1. Stop Odoo; restore DB `pg_restore -c -d {{db}} {{file}}`; restore filestore
2. Redeploy previous image/tag {{tag}}
