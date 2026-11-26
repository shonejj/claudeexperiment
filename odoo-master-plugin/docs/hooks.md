# Hooks

All hooks are declared in `hooks/hooks.json`. Each runs `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/hook.py <name>`, and the code is in
`scripts/odoo_master/hooks/`. Hooks read the JSON payload on stdin. They **fail open**: an internal error becomes a
one-line `systemMessage` plus an entry in `.odoo-master/logs/hook-errors.jsonl`, and never blocks the session.
Hooks are guard-rails; permissions and infrastructure are the security boundary (see `security.md`).

| Event | Matcher | Handler | Behaviour | Output used |
|---|---|---|---|---|
| SessionStart | `startup\|resume\|clear\|compact` | `session-start` | detects the Odoo version, counts modules, lists active executions (for resume), registered MCP capabilities and the autonomy mode; persists plugin options for the CLI | stdout → session context (≤ 2.6 KB) |
| UserPromptSubmit | — | `prompt` | detects ticket keys and GitHub/Slack/Linear links; adds intent hints (plan/estimate → estimator, fix → validator/runtime, migrate → migration tools, new module → scaffold); when version signals conflict and the prompt names exactly one series, records it as confirmed | `additionalContext` |
| PreToolUse | `Bash\|Edit\|Write\|MultiEdit\|NotebookEdit` | `guard` | git/database/deployment/secret rules; Odoo core-file protection; hard-coded secrets in edits; holds module edits while version signals conflict (until `detect-version --confirm`); snapshots pre-existing findings before the first edit of a file | `permissionDecision` deny/ask (ask → deny in `bypassPermissions`/`dontAsk`) |
| PostToolUse | `Edit\|Write\|MultiEdit` | `post-edit` | validates the edited Odoo file for the detected series (manifest, Python, XML refs, version rules) and records it in the session ledger | `additionalContext` (findings + fixes) |
| PostToolUse | `Bash` | `evidence-capture` | when `odoo-master validate`, `runtime test`, `migration scan` or `db overview` ran, stores the output as evidence (pass/fail parsed), attached to the single active execution or to `session-<id>` | files in `.odoo-master/evidence/` |
| PostToolUse | `mcp__.*` | `mcp-post` | logs MCP call metadata (tool, server, duration; no payloads) | `logs/mcp-calls.jsonl` |
| PostToolUseFailure | `mcp__.*` | `mcp-failure` | logs the failure (redacted), marks the server in the registry, tells the agent how to degrade safely | `additionalContext` |
| SubagentStart | `odoo-master:.*` | `subagent-start` | injects series, conflicts, active execution/ticket, instruction and CLI pointers into every plugin specialist | `additionalContext` |
| SubagentStop | `odoo-master:.*` | `subagent-stop` | enforces the reporting contract (`STATUS: DONE\|DONE_WITH_CONCERNS\|NEEDS_CONTEXT\|BLOCKED`): one re-prompt if it is missing; logs statuses | `decision: block` + reason |
| Stop | — | `stop-gate` | validates the Odoo files changed this session; blocks only on errors **introduced** this session (pre-existing findings are snapshotted by the guard before the first edit of each file), max 3 times; once per session asks for a validation run when Odoo files changed without one (`policies/testing.yaml`) | `decision: block` + reason |
| PreCompact | `manual\|auto` | `pre-compact` | writes the session ledger and tells compaction what to keep (execution and ticket ids, approvals, version, verification levels) | stdout → compaction instructions |
| SessionEnd | — | `session-end` | appends a session summary (files changed, gate blocks, agent statuses, active executions) | `logs/sessions.jsonl` |

## Verified in real Claude Code sessions
`tests/live/run_live_sessions.py` (headless `claude -p --plugin-dir`, stream-json with hook events) verified that
SessionStart context is injected, the guard denies `git push --force`, post-edit feedback makes Claude replace `attrs`
with 17+ syntax by itself, SubagentStart/SubagentStop fire for plugin agents and record `STATUS: DONE`, and slash
commands run. Hook logic is also covered by `tests/test_hooks.py` and `tests/test_v2_features.py` through subprocess payloads.

## Disabling
Turn off all plugin hooks by disabling the plugin. For finer control, managed settings can disable plugin hooks;
`policies/testing.yaml` → `quality_gate.enabled: false` turns off only the Stop gate.
