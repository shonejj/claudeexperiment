---
title: "Migration plan — {{modules}} {{source}} → {{target}}"
kind: migration-plan
ticket: "{{ticket}}"
execution: "{{execution}}"
odoo_version: "{{target}}"
generated_at: "{{date}}"
---
# Migration plan — {{source}} → {{target}}

## Scope
Modules (dependency order): {{...}} · Hops: {{hops}} · Enterprise dependencies: {{...}}

## Findings (from `odoo-master migration plan`)
| Module | Blockers | Changes | Notable rules |
|---|---|---|---|

## Database implications
Stored field renames/removals, constraints (19.0), ACL format (20.0), data fixes, volumes.

## Plan per hop
### {{hop}}
1. Branch `migrate/{{hop}}`
2. `odoo-bin upgrade_code --from {{prev}} --to {{hop}} --dry-run` → review → apply
3. Fix remaining findings; bump versions; upgrade scripts
4. Validate: scan, static, runtime install; upgrade test on neutralized copy

## Validation queries
```sql
-- row counts / spot checks per affected table
```

## Risk assessment
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|

## Rollback strategy
Backup restore + previous release; decision criteria for rollback.

## Approvals
Production migration: human approval required (always_human).
