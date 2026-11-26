---
name: pull-request-review
description: "Reviewing an existing pull request end to end: fetch diff, files and CI status, check out the head in an isolated worktree, run Odoo validation on changed files, apply the two-verdict review, and post (after approval) a structured review. Use when asked to review a PR or on PR events."
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

# Pull request review

1. Fetch PR metadata, changed files, diff and checks (capability `repo.read_pull_request`, `repo.inspect_checks`).
2. Isolated checkout: `git fetch origin pull/<n>/head:pr-<n> && git worktree add ../pr-<n> pr-<n>` (or Agent `isolation: worktree`).
3. `odoo-master --root ../pr-<n> validate --files <changed> --brief`; `odoo-master --root ../pr-<n> detect-version --brief` (version mismatch with target branch is a finding).
4. Apply `code-review` (two verdicts) + security and database review when models/security change.
5. Draft the review: summary, blockers, suggestions with path:line, verification levels run (static vs runtime).
6. Post only after approval (external write); remove the worktree afterwards.
