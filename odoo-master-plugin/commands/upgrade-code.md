---
description: "Run Odoo's own `upgrade_code` rewriting scripts (18.0+ images) over the custom addons: dry run first, apply only after confirmation on a clean branch."
argument-hint: "<from> <to> [addons_dir]"
allowed-tools:
  - "Bash(odoo-master *)"
  - "Bash(git diff*)"
  - "Bash(git status*)"
disable-model-invocation: true
---

1. Dry run: `odoo-master source upgrade-code $2 --from $0 --to $1` and show the files that would change.
2. Ask for confirmation. On a clean working tree on a migration branch, apply with `--apply`.
3. Show `git diff --stat`, review the rewrites (they are best-effort), then run `odoo-master validate --series $1 --brief` and `odoo-master migration scan --from $0 --to $1`.
