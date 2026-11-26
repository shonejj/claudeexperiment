# GitHub integration

- **Repository intelligence**: `odoo-master analyze` reads git state, the default branch and remotes (credentials stripped).
- **Branches**: `odoo-master/<ticket>-<slug>` from the default branch. The guard hook blocks force pushes and asks before destructive git commands.
- **Pull requests**: `github-agent` uses `repo.create_pull_request` (GitHub MCP) or `gh` when authorised. The body follows the repository's PR template when one exists, and links the ticket and evidence.
- **CI**: `repo.inspect_checks` reads check runs and logs. Failures are summarised for QA.
- **Reviews**: the `pull-request-review` workflow checks out the PR head in a worktree, validates it, reviews it from several angles, and posts after approval.
- **Events**: GitHub webhooks (issues, pull_request, check_suite/check_run) go to `/events/github` with `X-Hub-Signature-256` and secret `ODOO_MASTER_GITHUB_WEBHOOK_SECRET`. Routes map labels to `github-issue-development` and opened PRs to `pull-request-review` (disabled by default).
- Never merge, force-push or delete branches without explicit approval (`policies/git-safety.yaml`, `approvals.yaml`).
