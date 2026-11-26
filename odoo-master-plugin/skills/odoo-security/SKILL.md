---
name: odoo-security
description: "Odoo access control and application security: groups and privileges, ACL CSV formats (ir.model.access up to 19, ir.access in 20), record rules and multi-company domains, field groups, sudo/with_user, public routes, SQL injection, secrets. Use when creating models, changing access, or reviewing security."
---

# Odoo security

## ACLs
≤19.0 `security/ir.model.access.csv`:
```
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_quality_check_user,quality.check user,model_stock_quality_check,stock.group_stock_user,1,1,1,0
access_quality_check_manager,quality.check manager,model_stock_quality_check,stock.group_stock_manager,1,1,1,1
```
20.0+ `security/ir.access.csv` (ACLs and rules merged; `operation` ⊆ `crud`; optional `domain` restricts):
```
id,name,model_id,group_id/id,operation,domain
access_quality_check_user,quality.check user,stock.quality.check,stock.group_stock_user,cru,
access_quality_check_own,own checks,stock.quality.check,base.group_portal,r,"[('partner_id', '=', user.partner_id.id)]"
```
## Record rules (≤19.0)
```xml
<record id="quality_check_company_rule" model="ir.rule">
    <field name="name">Quality checks: multi-company</field>
    <field name="model_id" ref="model_stock_quality_check"/>
    <field name="domain_force">[('company_id', 'in', company_ids)]</field>
</record>
```
Global rules (no `groups`) are intersected; group rules are unioned. Test as regular users (`with_user`): `sudo()` (superuser) bypasses ACLs and rules, so tests run only as superuser prove nothing about access.

## Groups
≤18: `category_id` for app sections; **19+**: `res.groups.privilege` (`privilege_id`) groups groups per app. Users field `group_ids` (19+, `groups_id` before).

## Checklist (review)
- Every new non-abstract model has ACLs; transient models too.
- No ACL without group unless it is truly global (portal/public!).
- `sudo()` scope justified and narrow; no `sudo()` + user-supplied domain.
- `cr.execute(query, params)` / `odoo.tools.SQL`; never `%`/f-strings into SQL. No `eval` on data.
- Controllers: auth level, csrf, input validation, IDs checked with `check_access`.
- Secrets in `ir.config_parameter`/env, never in code or data files.
Run: `odoo-master validate --modules <m> --brief` (acl-*, rule-*, py-sql-injection, py-eval rules).
