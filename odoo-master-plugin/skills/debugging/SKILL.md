---
name: debugging
description: "Systematic root-cause debugging for Odoo and general code: reproduce, read the traceback and logs, form and test hypotheses, locate the responsible module and override chain, fix with a regression test. Use for any error, traceback, failing test or wrong behaviour."
---

# Debugging

1. **Reproduce**: failing test (preferred), runtime log (`odoo-master runtime test` / user log), or exact steps. No reproduction → gather more data, do not guess-fix.
2. **Read the evidence**: `odoo-master logs summarize <log>` — first traceback, PostgreSQL errors, module loading order.
3. **Locate**: frame paths → module (custom vs standard); override chain for the method (`_inherit` across modules, MRO); recent commits touching the area (`git log -p -- <path>`).
4. **Hypothesise → test** one at a time (add a focused test or log line on a test db).
5. **Root cause** statement with path:line evidence, and why it was not caught.
6. **Fix** at the cause, not the symptom; regression test fails before and passes after.
Common Odoo causes: missing `super()`, wrong `@api.depends`, access errors from missing ACL/rules, XPath target missing after upgrade, `attrs` on 17+, `_sql_constraints` ignored on 19+, cache/prefetch issues after raw SQL (`invalidate_model()`), multi-company `check_company`.
