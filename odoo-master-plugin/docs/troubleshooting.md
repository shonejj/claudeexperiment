# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `odoo-master: command not found` | plugin disabled, or used outside Claude Code | enable the plugin, or call `${CLAUDE_PLUGIN_ROOT}/bin/odoo-master` / the full path |
| `PyYAML is not installed` | missing dependency | `python3 -m pip install pyyaml jsonschema` or set `ODOO_MASTER_PYTHON` |
| Version "unknown" or CONFLICTS at session start | no strong signals, or partially migrated code | `odoo-master detect-version` to see signals; confirm the series; set `default_odoo_version` |
| `xml-ref-module-not-in-depends` on a valid ref | dependency from a third-party/OCA module not in the repository | add that repository to the scanned tree, or treat as info; the standard graph only covers Community |
| `runtime: skipped — docker daemon not reachable` | Docker not running or not permitted | start Docker / add the user to the docker group; or accept that the runtime level is missing |
| Runtime install fails with `could not translate host name "db"` | custom image entrypoint | the runner passes `HOST/USER/PASSWORD` like the official image; custom images must honour them or set `runtime.image` |
| `passed_no_tests` | module has no tests or tags filtered them out | add tests or fix `--test-tags`; this is not a pass |
| Visual QA hangs on load | Odoo websocket keeps the network busy | the script waits for the web client, not network idle; check `report.json` for login errors |
| PDF engine `reportlab` used | Node/Playwright and Chrome unavailable | install Playwright (`npx playwright install chromium`) for styled PDFs |
| MCP capability not found | server not registered or not connected | run the `mcp-integration` skill: list tools, `mcp register`, or connect the server (`/mcp`) |
| Webhook returns 401 | secret env var not set, or signature mismatch | set `ODOO_MASTER_*_SECRET`; check the signing header name in routes |
| Stop hook keeps blocking | validation errors in files changed this session | fix them, or explain; after 3 blocks the gate reports instead (`policies/testing.yaml`) |
| Hook error message "error (ignored)" | internal hook exception (fail-open) | see `.odoo-master/logs/hook-errors.jsonl` |
