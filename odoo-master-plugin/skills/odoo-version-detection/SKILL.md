---
name: odoo-version-detection
description: "Determines the Odoo series (16.0-20.0+) of a project from multiple signals (odoo/release.py, Docker images, requirements, manifests, syntax fingerprints) with confidence and conflict reporting, and loads the matching version rules. Use before writing or reviewing any Odoo code, and whenever versions are ambiguous."
---

# Odoo version detection

Result now: !`"${CLAUDE_PLUGIN_ROOT}/bin/odoo-master" detect-version --brief 2>/dev/null || true`

- Full evidence: `odoo-master detect-version` (signals with weights and file:line, fingerprint bounds, conflicts).
- Priority: `odoo/release.py` (100) > Docker image tag (80) > requirements/odoo-version file (60) > manifest majority (40) > syntax fingerprints (bounds only).
- **Conflicts** (e.g. manifests say 18.0 but views still use `attrs`) mean partially migrated code or wrong metadata: stop and ask which series is targeted.
- Unknown version and no config fallback → ask; never guess.

## Then load the rules for that series
`${CLAUDE_PLUGIN_ROOT}/knowledge/odoo-versions.yaml` (machine-readable) and `${CLAUDE_PLUGIN_ROOT}/docs/research/odoo-version-compatibility.md` (human table). Key breaks:
| Since | Change |
|---|---|
| 17.0 | `attrs`/`states` rejected → `invisible=`/`readonly=`/`required=` expressions; init hooks take `env` |
| 18.0 | `<tree>` → `<list>`, `view_mode` `list`; `check_access()`; `aggregator` (was `group_operator`) |
| 19.0 | `_sql_constraints` ignored → `models.Constraint`/`models.Index`; `type='jsonrpc'`; `groups_id` → `group_ids` (users, menus, views, actions); `res.groups.privilege`; `odoo.osv` deprecated; `self.env.cr` not `self._cr` |
| 20.0 | `ir.access` replaces `ir.model.access` + `ir.rule` (`ir.access.csv`: `id,name,model_id,group_id/id,operation,domain`); OWL 3; Python ≥ 3.12 |
