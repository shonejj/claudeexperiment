# Slash commands

Commands live in `commands/*.md` and run as `/odoo-master:<name>`. They are user-triggered shortcuts (`disable-model-invocation: true`) over the skills and the `odoo-master` CLI. Each one pre-approves only the commands it needs through `allowed-tools`, and live facts are injected with a single `` !`odoo-master --soft ...` `` command, so they work in the default permission mode.

Skills are slash commands too (`/odoo-master:<skill>`). See `skills.md`. Command names never collide with skill names; a test checks this.

| Command | Arguments | What it does |
|---|---|---|
| `/odoo-master:analyze` | `[focus]` | Analyse the current repository: Odoo version (with evidence), custom modules, standard models extended, findings and knowledge limits. |
| `/odoo-master:approve` | `<execution-id> <step> [approve|reject] [note]` | Record a human approval (or rejection) for a workflow gate after showing what is being approved. |
| `/odoo-master:build` | `<request>` | Implement a feature or change end-to-end through the matching workflow (intake, plan, approval, implementation, tests, review, evidence, report). |
| `/odoo-master:doctor` | `` | Check the environment for Odoo Master: Python deps, Docker + images, Node/Playwright, psql, LSP server, Claude Code version, state directory. |
| `/odoo-master:events` | `[setup|check|records]` | Set up or check event-driven automation (Jira/GitHub/Slack/Linear webhooks → workflows): routes, secrets, receiver, recorded executions. |
| `/odoo-master:fix` | `<symptom, error or traceback>` | Fix a bug in an existing Odoo customisation: reproduce, root cause with evidence, regression test, fix, verify, review. |
| `/odoo-master:init` | `[--events] [--settings]` | Initialise Odoo Master in this project: config file, optional event routes, optional recommended permissions in .claude/settings.json (backup first). |
| `/odoo-master:lookup` | `<model|module> <name> [--series 18.0]` | Where is a standard Odoo model or module defined, what extends it, and what does the standard source look like (official image, no clone). |
| `/odoo-master:mcp` | `[probe|register|resolve <capability>]` | Discover connected MCP servers and their tools, classify capabilities (ticket/repo/chat/docs/db/browser) and register them for workflows. |
| `/odoo-master:migrate` | `<from> <to> [modules]` | Analyse and plan (then, after approval, perform) a migration of custom modules between Odoo versions, one hop at a time. |
| `/odoo-master:plan` | `<what to build or change>` | Plan a change without implementing it: requirements, reuse decision, technical design, module and database impact, estimate and risks; render a PDF; ask for approval. |
| `/odoo-master:report` | `<file.md> [--formats html,pdf]` | Render a Markdown plan/report to HTML and a verified PDF. |
| `/odoo-master:resume` | `[execution-id]` | Resume a workflow execution after a pause, approval, compaction or new session. |
| `/odoo-master:review` | `[base-ref]` | Independent review of the current branch: static validation plus two-verdict review (spec, quality) and security/database review in parallel. |
| `/odoo-master:scaffold` | `<module_name> [--model x.y] [--depends a,b] [--series 19.0]` | Create a new, version-correct Odoo module skeleton (model, views, security, menu, tests) for the detected or given series, then validate it. |
| `/odoo-master:status` | `` | Show the Odoo Master dashboard: version, active workflow executions, pending approvals, MCP integrations, runtime instances, recent webhook events. |
| `/odoo-master:test` | `<module[,module2]> [--series 18.0]` | Install and upgrade modules in a disposable Odoo + PostgreSQL (Docker) and run their Odoo tests; report counts honestly. |
| `/odoo-master:ticket` | `<KEY-123 or URL> [plan|implement]` | Plan or implement a ticket (Jira, Linear, GitHub issue) end to end via the connected MCP servers, keeping the ticket id on every artifact. |
| `/odoo-master:upgrade-code` | `<from> <to> [addons_dir]` | Run Odoo's own `upgrade_code` rewriting scripts (18.0+ images) over the custom addons: dry run first, apply only after confirmation on a clean branch. |
| `/odoo-master:validate` | `[module,module2] [--series 18.0]` | Run Odoo static validation (manifest, XML/XPath, references, security, Python, JS, version rules) and explain/fix the findings. |

## Typical sequences
```
/odoo-master:init                 # once per project (config; optional events/permissions)
/odoo-master:doctor               # what is available here (Docker, Playwright, psql, LSP)
/odoo-master:analyze              # facts, version, modules, knowledge limits
/odoo-master:plan <change>        # plan + estimate + PDF, no code
/odoo-master:approve <exec> <step>
/odoo-master:build <change>       # full workflow; or /odoo-master:fix <bug>
/odoo-master:test <module>        # runtime install + upgrade + tests
/odoo-master:review               # parallel reviewers
/odoo-master:status               # executions, pending approvals, MCP, runtime instances
```
