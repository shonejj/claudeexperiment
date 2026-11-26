---
name: evidence-generation
description: "Collecting verifiable evidence for a workflow execution: validation reports, runtime test results, logs summaries, screenshots, review verdicts and commands, hashed into an evidence manifest with achieved and missing verification levels. Use whenever work is verified or before claiming completion."
---

> CLI: `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` — use this absolute path (the plugin's `bin/` is not on PATH in every environment); `odoo-master` below is shorthand for it.

# Evidence generation

- Add items as they are produced:
  `odoo-master evidence add -e <execution> --kind validation|unit-test|runtime-test|browser-check|screenshot|review|migration-check|log-summary|database-check|command|report --level static|unit|integration|runtime|database|browser|production --path <file> --status passed|failed|skipped|passed_no_tests|info --summary "..."`
- Runtime tests write their own evidence JSON (`.odoo-master/evidence/runtime-test-<id>.json`); add it to the execution with `--path`.
- `odoo-master evidence manifest -e <id>` → manifest with sha256 per file and `levels_achieved` / `levels_missing` (against policies/testing.yaml for the workflow intent).
- `odoo-master evidence verify -e <id>` → re-hashes files; any mismatch or missing file fails.
- Final reports quote the manifest; never upgrade a `skipped` level to `passed`.
