---
name: github-management
description: "GitHub operations via the GitHub MCP server or gh CLI when authorised: repository discovery, default branch, branches, issues, pull requests (create/update with ticket links), CI check inspection and review comments, with git safety rules. Use for branch, PR, issue and CI steps."
---

# GitHub management

- Capabilities: `repo.read_issue`, `repo.create_branch`, `repo.create_pull_request`, `repo.update_pull_request`, `repo.inspect_checks`, `repo.add_comment`, `repo.read_pull_request` (`odoo-master mcp resolve <cap>`). Fallback: `gh` CLI if installed and authenticated; otherwise local git only.
- Branch: `odoo-master/<ticket>-<slug>` from the default branch (`project-inventory.json` → git.default_branch). Preserve uncommitted user changes.
- Push: `git push -u origin <branch>` — never `--force`; never push to protected branches (`policies/git-safety.yaml`).
- PR body: summary, ticket link, changes per module, tests + verification levels, migration notes, evidence links, open issues. Search for a PR template first (`.github/pull_request_template.md`).
- CI: read check runs; summarise failures with job/log excerpts for the qa-engineer.
- Never merge, close or delete without explicit approval.
