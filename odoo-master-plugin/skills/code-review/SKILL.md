---
name: code-review
description: "Independent two-verdict code review (spec compliance + quality) of a diff with Odoo-aware checks: version rules, super() in overrides, ACLs and rules, batching, migrations for stored fields, tests, security, and running the validator. Use after implementation steps, before PRs, or when asked to review."
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

# Code review

Input: diff (`git diff <base>...HEAD`), spec/acceptance criteria, validation evidence.

1. Run `odoo-master validate --files <changed files> --brief` yourself.
2. Read changed code **and** surrounding code (callers, overrides, views using the fields).
3. **Verdict 1 — spec compliance**: each acceptance criterion implemented? tested? anything extra/unrequested?
4. **Verdict 2 — quality**:
   - correctness & edge cases (empty recordsets, multi-record `self`, multi-company);
   - version-correct APIs (see odoo-version-detection table);
   - overrides call `super()`; computes assign all records; `@api.depends` complete;
   - security: ACLs, rules, sudo scope, SQL params, controller auth/csrf;
   - performance: no queries in loops, indexes for searched fields;
   - data: stored field changes have upgrade scripts + version bump;
   - tests meaningful (fail without the change), not testing the framework.
5. Findings ranked (blocker / major / minor / nit) with path:line and concrete fix.
Output:
```
SPEC: PASS|FAIL   QUALITY: PASS|FAIL
1. [blocker] path:line — problem — fix
```
