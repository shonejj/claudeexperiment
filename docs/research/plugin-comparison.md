# Reference plugin comparison

Research date: 2026-11-25. Sources were read from the projects' GitHub pages and READMEs
(links below). Benchmarks quoted by the projects are **self-reported** and were not re-run here.

## Identification of the named projects

| Name in brief | Project identified | Repo | License | Confidence |
|---|---|---|---|---|
| Superpowers | Superpowers by Jesse Vincent | https://github.com/obra/superpowers | MIT | Confirmed by user |
| Caveman | Caveman by Julius Brussee | https://github.com/JuliusBrussee/caveman | Apache-2.0 (+ MIT file) | Confirmed by user |
| Ponytail | Ponytail by Dietrich Gebert | https://github.com/DietrichGebert/ponytail | MIT | High: only Claude Code plugin by that name |
| Tast | **taste-skill** by Leonxlnx (assumed spelling of "taste") | https://github.com/Leonxlnx/taste-skill | MIT | Medium: no project named exactly "tast" exists; taste-skill is the dominant match |

Odoo-specific projects surveyed:

| Project | Repo | License | Notes |
|---|---|---|---|
| unclecatvn/agent-skills | https://github.com/unclecatvn/agent-skills | MIT | Per-version Odoo skill packs 16–19, trace-first workflow, reviewer + tracer agents |
| EdgarNaranjo/agent-skills (pi-odoo-workflow) | https://github.com/EdgarNaranjo/agent-skills | LGPL-3.0+ | Prompt templates `/odoo-*`, 18/19 only, version asked not detected |
| Viindoo "Odoo AI Agent Team" | odoo-semantic.viindoo.com | unknown | **Not read** (host blocked from this environment) |
| ahmed-lakosha/odoo-plugins, hawkeg, sickn33 bundle, mart337i, wpmoo-org | listed on claudepluginhub / claudemarketplaces | mostly MIT | Seen only in directory listings; not inspected in depth |

## What each project does well, and its limits

### Superpowers (process framework)
- **Mechanics.** 15 skills (`brainstorming`, `writing-plans`, `executing-plans`,
  `subagent-driven-development`, `dispatching-parallel-agents`, `using-git-worktrees`,
  `test-driven-development`, `systematic-debugging`, `verification-before-completion`,
  `requesting-code-review`, `receiving-code-review`, `finishing-a-development-branch`,
  `using-superpowers`, `writing-skills`, `diagnosing-superpowers`). A `SessionStart` hook
  (`matcher: startup|clear|compact`) re-injects the bootstrap skill, including after compaction.
- **Subagent-driven development.** A fresh implementer subagent per plan task, brief extracted to a
  file, a task reviewer returning *two verdicts* (spec compliance + quality), a final whole-branch
  review. Implementers report one of four statuses: `DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`,
  `BLOCKED`. A ledger `progress.md` survives compaction. Review diffs use a recorded BASE commit.
- **Adopt:** status vocabulary, ledger file, two-verdict review, bootstrap re-injection on
  `compact`, plan tasks with exact file paths and verification steps, "verify before claiming done".
- **Improve:** Superpowers is domain-agnostic. It has no notion of environment facts (versions,
  databases), no external ticket systems and no approval policy beyond conversation.
- **Reject:** mandatory TDD that deletes code written before tests — Odoo customisations frequently
  extend framework behaviour that is only testable via install/upgrade; we require tests but allow
  test-after when the change is an XML/view-only change.

### Ponytail (write-less-code discipline)
- **Mechanics.** One core prompt applying a "ladder": does it need to exist → already in codebase →
  stdlib → native platform feature → installed dependency → one line → minimum that works (+ one test
  for risky logic). Every reply lists what was skipped/unchecked. Hooks inject the active mode at
  session start; `ponytail-review`, `ponytail-audit`, `ponytail-debt` (collects `shortcut:` comments).
- **Adopt:** the ladder maps almost exactly onto Odoo's "extension point first" rule: *does standard
  Odoo already do this? → is there an existing custom module to extend? → can it be done with
  inheritance/xpath/data? → only then new code*. We encode this as the **Odoo reuse ladder** in
  `instructions/odoo-development.md`. Also adopt the "report what was skipped/unchecked" ending.
- **Improve:** Ponytail's ladder is prose-only; ours is backed by deterministic inventory scripts that
  tell the agent what modules/models already exist.

### Caveman (token economy)
- **Mechanics.** Terse output voice (several levels), compression of tool output (logs, CSV, JSON,
  test output) before the model reads it, a `caveman-compress` skill for memory files.
- **Adopt:** our scripts emit **compact JSON summaries** instead of raw logs (e.g. `odoo_log_summary`
  collapses an Odoo server log to errors/warnings/tracebacks with counts). Hook-injected context is
  capped in size.
- **Reject:** terse prose voice for deliverables — plans, Jira comments and reports are read by
  humans and must be complete sentences. Also reject telemetry and cloud routing (Caveman CLI sends
  usage telemetry by default; our plugin sends nothing anywhere).

### taste-skill ("Tast")
- **Mechanics.** Encodes design rules **as code**, not prose: deterministic Node scripts render the
  page in headless Chrome at several widths and print PASS/WARN/FAIL per rule; a `gate.mjs` Stop
  hook blocks finishing while fixable FAILs remain (max 3 rounds).
- **Adopt:** the *gate pattern*. Our `Stop` hook runs `quality-gate.py` over Odoo files changed in the
  session (manifest/XML/security/Python syntax). Errors block stopping with a bounded number of
  rounds (Claude Code itself caps consecutive Stop-blocks). Our visual QA uses Playwright screenshots
  at multiple viewport widths, and reports console/network errors per page.
- **Reject:** opinionated house aesthetic. Odoo backend UI follows Odoo's own design system; we
  check for regressions, not "taste".

### unclecatvn/agent-skills (most complete Odoo prior art)
- **Mechanics.** Per-version knowledge packs (`skills/odoo-16.0` … `odoo-19.0`), a trace helper
  (`odoo_trace.py`) that resolves where a model/field/method really comes from in the Odoo source,
  a "Context Brief" in which every claim has `file:line` or `NOT FOUND/UNCERTAIN`, and a definition of
  done that requires >0 tests run on a throwaway `scratch_<module>` database. Version from
  `odoo/release.py`; stops when sources disagree.
- **Adopt:** evidence-cited context brief; version from `release.py` as the authoritative source;
  stop-on-conflict; scratch databases for tests; "0 tests ran" is a failure, not a pass.
- **Improve:** it needs a local Odoo checkout. Ours degrades gracefully: we detect version from (in
  order) `release.py`, Docker image tags, `odoo.conf`/requirements pins, manifest version prefixes,
  and syntax fingerprints — and report the confidence and which sources agreed. We also add database
  intelligence, migrations, MCP/ticket integration and an approval policy, none of which it has.

### EdgarNaranjo / pi-odoo-workflow
- Good catalogue of task prompts (`/odoo-module`, `/odoo-migrate`, `/odoo-qa`, …) and a "explain
  before coding" rule. Version is *asked*, not detected; Claude Code receives only skill text.
  We adopt the idea of one entry skill per task family, but drive it by detected facts.

## Design synthesis: how Odoo Master improves on these

| Concern | Prior art | Odoo Master |
|---|---|---|
| Version awareness | asked (Edgar) or release.py only (unclecat) | multi-source detector with confidence + conflict report; per-version rule table verified against real 17/18/19/20 source |
| Understanding existing repos | trace helper | full inventory → `.odoo-master/*.json` (modules, models, inherits, views, ACLs, deps graph, cycles, missing deps) |
| Process | Superpowers brainstorm→plan→SDD | workflow YAMLs (schema-validated) with approval gates, checkpoints/resume, driven by `workflow_engine.py` |
| Quality gate | taste gate.mjs | Odoo static validators + Stop-hook gate + runtime test runner (Docker) |
| Reuse discipline | Ponytail ladder | Odoo reuse ladder backed by inventory facts |
| Token economy | Caveman | compact JSON script outputs, log summariser, capped hook context |
| External systems | none | MCP capability registry (runtime discovery, read/write classification), ticket lifecycle, webhook receiver |
| Safety | prompts | PreToolUse guard hook (destructive SQL, force-push, production DB, secrets) + policies YAML + native permissions |
| Evidence | none / ad hoc | evidence manifest with SHA-256 per artifact, Markdown + PDF reports |

Licensing: no code was copied from any of the projects above. Ideas adopted are credited here.
