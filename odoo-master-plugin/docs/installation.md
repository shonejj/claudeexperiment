# Installation

## Requirements
| Need | For | Required? |
|---|---|---|
| Claude Code ≥ 2.1.300 (developed and validated on 2.1.332) | plugin, hooks, skills, agents | yes |
| Python ≥ 3.10 with PyYAML | the `odoo-master` core, hooks | yes (jsonschema recommended for full schema validation) |
| git | repository analysis, branches | yes |
| Docker | runtime install/upgrade tests, visual QA instances | optional — runtime levels are reported as missing without it |
| Node ≥ 18 + Playwright (Chromium) | visual QA, best PDF rendering | optional — PDF falls back to Chrome CLI, then ReportLab |
| `psql` client | read-only database inspection | optional |
| pypdf | PDF page-count verification | optional |
| `pyright-langserver` (`npm i -g pyright`) | Python diagnostics via the plugin's `.lsp.json` | optional |
| bubblewrap + socat | running `claude plugin eval` (sandboxed shell) | only for evals |

## Install from this repository's marketplace
Inside Claude Code:
```
/plugin marketplace add shonejj/claudeexperiment
/plugin install odoo-master@odoo-master
```
Or from a shell:
```
claude plugin marketplace add shonejj/claudeexperiment
claude plugin install odoo-master@odoo-master
```
Local development without installing: `claude --plugin-dir /path/to/claudeexperiment/odoo-master-plugin`.

Then set plugin options (autonomy, production patterns, fallback version):
```
claude plugin configure odoo-master
```

## Project setup
```
/odoo-master:init                 # .odoo-master/config.yaml
/odoo-master:init --events        # + webhook routes
/odoo-master:init --settings      # + recommended permissions merged into .claude/settings.json (backup first)
/odoo-master:doctor               # what works in this environment
```

## Verify
```
claude plugin validate /path/to/odoo-master-plugin
odoo-master --help                       # on PATH while the plugin is enabled (plugin bin/)
odoo-master runtime check                # Docker reachable?
cd your-odoo-repo && odoo-master analyze --brief
```
Start a session in an Odoo repository. The SessionStart hook prints the detected version and the entry points.

## Python dependencies
```
python3 -m pip install pyyaml jsonschema pypdf    # pypdf optional
```
To use another interpreter, set `ODOO_MASTER_PYTHON=/path/to/python`.

## Optional: Enterprise addons for runtime tests
Point runtime tests at a local Enterprise checkout (mounted read-only):
`odoo-master runtime test --modules m --enterprise /path/to/enterprise`, or set `runtime.enterprise_path` in `.odoo-master/config.yaml`.
