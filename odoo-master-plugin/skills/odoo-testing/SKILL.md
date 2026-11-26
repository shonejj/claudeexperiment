---
name: odoo-testing
description: "Testing Odoo modules: static validation with odoo-master, Python tests (TransactionCase, HttpCase, Form, tagged), JS tests and tours, running install/upgrade test passes in ephemeral Docker databases, reading results, and recording evidence. Use whenever code changes need verification."
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

# Odoo testing

## Levels (always report which ran)
| Level | How | Tool |
|---|---|---|
| static | manifest/XML/security/Python/version rules | `odoo-master validate --modules m --brief` |
| unit/integration (Odoo) | Python tests inside Odoo | `odoo-master runtime test --modules m` |
| runtime install/upgrade | `-i` then `-u` with `--test-tags /m` | same (two passes) |
| browser | tours / Playwright | `visual-qa` skill |
| database | read-only checks on an authorised copy | `odoo-database-analysis` |

## Writing tests
```python
from odoo.tests import Form, TransactionCase, tagged

@tagged("post_install", "-at_install")
class TestQuality(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].create({"name": "Stock user", "login": "stock_u",
            "group_ids": [(6, 0, [cls.env.ref("stock.group_stock_user").id])]})   # groups_id on ≤18

    def test_user_can_pass_check(self):
        check = self.env["stock.quality.check"].with_user(self.user).create({...})
        check.action_pass()
        self.assertEqual(check.state, "pass")
```
- Tests in `tests/` imported by `tests/__init__.py`; file names `test_*.py`.
- Test as real users (`with_user`) for access-related behaviour; `Form()` simulates onchanges; `assertQueryCount` guards performance.
- Do not depend on demo data (not loaded by default since 19.0); create fixtures in `setUpClass`.
- `--test-tags` syntax: `[-][tag][/module][:class][.method]`, e.g. `/stock_quality_check:TestQuality.test_user_can_pass_check`.

## Runtime runner
`odoo-master runtime test --modules m [--series 18.0] [--addons path1,path2] [--enterprise path] [--no-upgrade]`
- Ephemeral postgres + `odoo:<series>` containers, database `om_test_<id>`, addons mounted read-only, logs in `.odoo-master/logs/`, result in `.odoo-master/evidence/runtime-test-<id>.json`.
- Status `passed_no_tests` is **not** a pass (policy `zero_tests_is_failure`).
- Docker unavailable → record `runtime` as missing; do not claim it.
- Failures: `odoo-master logs summarize <log>` → classify (code/test/environment) → back to the developer with the excerpt.
