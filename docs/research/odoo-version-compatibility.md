# Odoo version compatibility

Research date: 2026-11-25.

**How this was verified.** www.odoo.com is blocked from the build environment, so the documentation
was read from its source repository, https://github.com/odoo/documentation (branches `16.0`, `17.0`,
`18.0`, `19.0`, `master`). Facts marked **[src]** were checked in the Odoo source shipped inside the
official Docker images `odoo:17.0`, `odoo:18.0`, `odoo:19.0` and `odoo:20.0` (pulled 2026-11-25),
under `/usr/lib/python3/dist-packages/odoo`.

The machine-readable version of this table is
`odoo-master-plugin/knowledge/odoo-versions.yaml`. It is used by `detect_version.py` and by
`validate_module.py` to pick version rules.

## Support status

Source: `content/administration/standard_extended_support.rst` (master).

| Version | Released | End of standard support | Python (min) | Notes |
|---|---|---|---|---|
| 20.0 | Sep 2026 | Sep 2029 (planned) | 3.12 (`source.rst`, master) | current major |
| 19.0 | Sep 2025 | Sep 2028 (planned) | 3.10 | image ships 3.12 |
| 18.0 | Oct 2024 | Sep 2027 (planned) | 3.10 | |
| 17.0 | Nov 2023 | Sep 2026 → extended support only | 3.10 | |
| 16.0 | Oct 2022 | Sep 2025 → extended support only | 3.7 | PostgreSQL ≥ 12 |
| SaaS x.1–x.4 | every 2–3 months | Odoo Online only | | not installable on-premise |

Upgrades through upgrade.odoo.com are possible to any major version still in standard support, or
one that left it less than six months ago.

## Breaking changes by version (what the agents must apply)

| Area | 16.0 | 17.0 | 18.0 | 19.0 | 20.0 |
|---|---|---|---|---|---|
| Release file | `odoo/release.py` | same | same | same | same |
| ORM package | `odoo/models.py` | same | same | **`odoo/orm/`** package (`odoo/orm/models.py`) [src] | same |
| View visibility | `attrs`, `states` allowed | **`attrs`/`states` rejected**: "Since 17.0, the "attrs" and "states" attributes are no longer used" [src `ir_ui_view.py`]; use `invisible="expr"`, `readonly=`, `required=` | same | same | same |
| List view tag | `<tree>`, `view_mode="tree,form"` | same | **`<list>`**, `view_mode="list,form"` (`upgrade_code/17.5-01-tree-to-list.py`) [src] | same | same |
| Display name | `name_get()` | `name_get` deprecated since 16.4; use `display_name` / `_compute_display_name` | `_search_display_name` | same | same |
| Access checks | `check_access_rights` + `check_access_rule` | same | **`check_access(op)`**, `has_access`, `_filtered_access` [src `models.py:4442`] | same | same |
| SQL constraints | `_sql_constraints = [...]` | same | same (18.1 introduced `models.Constraint`) | **`_sql_constraints` no longer supported** — logged warning and ignored [src `orm/model_classes.py:162`]; use `_name_uniq = models.Constraint("UNIQUE(name)", "msg")`, `models.Index`, `models.UniqueIndex` | same |
| Init hooks | `pre_init_hook(cr)`, `post_init_hook(cr, registry)` | **`(env)`** for all three hooks | same | same | same |
| JSON controllers | `type='json'` | same | same | **`type='jsonrpc'`** (`upgrade_code/18.1-02-route-jsonrpc.py`) [src] | same |
| User groups field | `groups_id` | same | same | **`group_ids`** (+ `all_group_ids`) on `res.users` [src] | same |
| Group categorisation | `category_id` | same | same | **`res.groups.privilege`**, `privilege_id` on `res.groups` [src] | same |
| Domains | `odoo.osv.expression` | same | `odoo.Domain` API (18.1) | `odoo.osv` deprecated: "use odoo.fields.Domain" [src] | same |
| Read group | `read_group` | `_read_group` new signature (16.3) | same | `read_group` deprecated for `_read_group` / `formatted_read_group` (18.2) | same |
| Env shortcuts | `self._cr`, `self._uid`, `self._context` | same | same | deprecated → `self.env.cr`, `self.env.uid`, `self.env.context` | same |
| Access model | `ir.model.access` (CSV `ir.model.access.csv`) + `ir.rule` | same | same | same | **`ir.access`** merges ACLs and rules; CSV `ir.access.csv` columns `id,name,model_id,group_id/id,operation,domain`, `operation` ⊆ `crud`; `ir_rule.py` and `ir.model.access` are gone [src] |
| Frontend | OWL 2 (shared since 14 per docs) | OWL 2 | OWL 2 | OWL 2 | **OWL 3** (`upgrade_code/owl3-migration.py`) [src] |
| Binary fields | base64 | same | same | same | `BinaryValue` type (SaaS 19.3 / 20.0) |
| Demo data | loaded by default | same | same | not loaded by default (SaaS 18.3 change); use `--with-demo` | same |
| CLI | `scaffold`, `neutralize`, `populate`, `cloc` | + `db` subcommand group, `deploy`, `obfuscate` | + `upgrade_code` (present in `odoo/cli/` [src], documented from 19.0) | + `module`, `i` | + `duplicate` |
| Webclient port | `--gevent-port` (`longpolling_port` legacy name still in default conf) | same | same | same | same |

## Automated code upgrades

From 18.0 onward Odoo ships `odoo-bin upgrade_code --from X --to Y [--dry-run]`, which runs the
scripts in `odoo/upgrade_code/` (`17.5-01-tree-to-list.py`, `18.1-00-sql-constraint.py`,
`18.1-02-route-jsonrpc.py`, … `19.4-00-ir-access.py`, `owl3-migration.py`) over a given addons path
(`content/developer/reference/cli.rst`, 19.0). The migration specialist uses `--dry-run` first and
reviews every rewritten file, because the docs state these scripts are "best-effort".

## Detection signals (used by `detect_version.py`, in priority order)

1. `odoo/release.py` → `version_info` (authoritative; only when Odoo source is in or near the repo).
2. Docker: `FROM odoo:<ver>` / `image: odoo:<ver>` in Dockerfiles and compose files.
3. Odoo.sh / requirements hints: `odoo==`, `odoo<ver>` wheels, branch names such as `17.0`.
4. Module manifests: `version` beginning with `<major>.0.` (convention; it can be stale).
5. Code fingerprints (weak): `<list>` vs `<tree>`; `attrs=`; `type='jsonrpc'`; `models.Constraint`;
   `ir.access.csv`; `group_ids`; `_sql_constraints`.

Signals are combined into a verdict with confidence `high|medium|low` and a list of conflicts. When
strong signals disagree, the agents must stop and ask, as unclecatvn/agent-skills also does.
