# Odoo support

| Series | Detection | Validation rules | Standard module/model maps | Runtime tests (official image) | Notes |
|---|---|---|---|---|---|
| 16.0 | ✓ | ✓ | ✓ (544 modules) | `odoo:16.0` pulled and used for extraction | extended support only |
| 17.0 | ✓ | ✓ | ✓ (641) | `odoo:17.0` | standard support ended Sep 2026 |
| 18.0 | ✓ | ✓ | ✓ (689) | `odoo:18.0` — **live install + upgrade + tests verified** | |
| 19.0 | ✓ | ✓ | ✓ (700) | `odoo:19.0` | |
| 20.0 | ✓ | ✓ | ✓ (704) | `odoo:20.0` | `ir.access`, OWL 3 |
| SaaS x.y | maps to nearest major | rules by `since` | nearest major | — | Odoo Online only |

- Scaffolded modules (`odoo-master scaffold`) were install/upgrade/test-verified live on all five series. A live 17→18→19
  migration chain is recorded in `docs/testing.md`.
- Version facts were verified against the documentation sources (`odoo/documentation`) and the source code
  inside the official images; see `docs/research/odoo-version-compatibility.md`.
- **Community vs Enterprise**: detection works for both. Enterprise dependencies are flagged from a known
  module list. Runtime tests need your Enterprise addons path (`--enterprise`) for Enterprise modules. The
  plugin never modifies Community or Enterprise source.
- **Odoo.sh / self-hosted / Docker**: environment detection reads Dockerfiles, compose files, `odoo.conf`
  (secrets redacted), requirements and Odoo.sh markers.
- Adding a new series: add it under `versions:` in `knowledge/odoo-versions.yaml`, add rules with `since: "<series>"`,
  and regenerate `knowledge/standard-modules/*-<series>.json` with the extraction commands in `docs/testing.md`.
