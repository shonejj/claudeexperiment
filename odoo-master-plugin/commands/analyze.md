---
description: "Analyse the current repository: Odoo version (with evidence), custom modules, standard models extended, findings and knowledge limits."
argument-hint: "[focus]"
allowed-tools:
  - "Bash(odoo-master *)"
disable-model-invocation: true
---

Current analysis:
!`odoo-master --soft analyze --brief`

Read `.odoo-master/project-context.md` and summarise for the user:
1. Odoo version + confidence + the signals (cite files). If there are conflicts, say so and ask which series is targeted.
2. Custom modules (purpose, depends, models, views, tests) and which standard models they extend (and the standard module that defines each).
3. Findings: models without ACL, syntax/XML errors, dependency cycles, unknown dependencies, modules without tests.
4. Knowledge limits (code-level only unless a database was inspected).
Focus area (optional): $ARGUMENTS
