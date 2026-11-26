---
name: repository-analysis
description: "Analyses any git repository (Odoo or not): structure, git state, branches, recent history, environment files (Docker, compose, odoo.conf with secrets redacted, CI), conventions and existing instructions. Use when connecting a repository or before planning changes in unfamiliar code."
---

# Repository analysis

1. `odoo-master analyze --brief` (writes `.odoo-master/` knowledge files; secrets in configs are redacted).
2. Read `git` facts from `.odoo-master/project-inventory.json` → `git` (branch, default branch, dirty files, remotes without credentials, recent commits).
3. Read existing instructions: `CLAUDE.md`, `AGENTS.md`, `README*`, `CONTRIBUTING*`, `.github/` workflows. Project instructions override plugin defaults on style; never overwrite them.
4. Environment: `environment` section (Dockerfiles, compose, odoo.conf options, requirements, `.env` keys only, CI files, Odoo.sh markers).
5. Conventions: module naming prefix, manifest author/license, test layout, linters (`.pre-commit-config.yaml`, `setup.cfg`, `ruff.toml`, OCA `oca-*` config).
6. Uncommitted changes belong to the user: never discard them; work around them or ask.

Output: a short repository brief (stack, layout, conventions, risks) with path citations, and the knowledge limits.
