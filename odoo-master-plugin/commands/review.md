---
description: "Independent review of the current branch: static validation plus two-verdict review (spec, quality) and security/database review in parallel."
argument-hint: "[base-ref]"
allowed-tools:
  - "Bash(odoo-master *)"
  - "Bash(git diff*)"
  - "Bash(git log*)"
disable-model-invocation: true
---

Base ref: $ARGUMENTS (default: the repository's default branch).
Run `odoo-master validate --files <changed files> --brief`, then dispatch in parallel `odoo-master:code-reviewer`, `odoo-master:odoo-security-specialist` and (when models or data changed) `odoo-master:database-reviewer` with the diff. Merge findings ranked by severity with path:line and fixes. (For a scripted parallel review you can also run `/odoo-master:odoo-parallel-review`.)
