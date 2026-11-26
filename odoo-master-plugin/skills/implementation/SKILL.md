---
name: implementation
description: "Disciplined implementation of an approved plan: feature branch, small verified steps, tests with every behaviour change, minimal diffs, preserving unrelated changes, and running the validators after each step. Use for any code change once a plan is approved."
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

# Implementation

1. Confirm the plan is approved (execution gate APPROVED) and the branch is right (`git status`, `git switch -c odoo-master/<ticket>-<slug>` from the default branch if needed). Never discard the user's uncommitted work.
2. For each plan task: write/adjust the test → implement → `odoo-master validate --files <changed> --brief` → fix → next task.
3. Odoo specifics: follow `instructions/odoo-development.md` and the detected version rules; react to post-edit hook findings immediately.
4. Keep diffs minimal; no unrelated refactors; no new dependencies without approval (Ponytail-style ladder: existing code → stdlib → Odoo feature → installed dep → new code).
5. Commit in logical units with messages referencing the ticket key.
6. At the end: runtime test when Docker is available; list exactly what was and was not verified.
