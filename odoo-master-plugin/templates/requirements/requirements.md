---
title: "Requirements — {{title}}"
kind: requirements
ticket: "{{ticket}}"
execution: "{{execution}}"
odoo_version: "{{odoo_version}}"
generated_at: "{{date}}"
---
# Requirements — {{title}}

## 1. Context
- Requested by / source: {{source (ticket URL, chat thread, user)}}
- Odoo apps and flows involved: {{e.g. Inventory → Receipts (stock.picking, incoming)}}
- Companies / multi-company constraints: {{...}}

## 2. Current behaviour
| Aspect | Standard Odoo | Existing customisation | Evidence |
|---|---|---|---|
| {{...}} | {{...}} | {{module / none}} | {{path:line}} |

## 3. Requirements
| ID | User story / rule | Priority |
|---|---|---|
| R1 | As a {{role}} I want {{capability}} so that {{benefit}} | must |

## 4. Acceptance criteria
- [ ] AC1 — Given {{state}}, when {{action}}, then {{result}}.

## 5. Non-functional requirements
Volumes, performance, security/roles, audit trail, localisation, reporting.

## 6. Data
New data, migrated data, imports, retention.

## 7. Open questions (with proposed defaults)
1. {{question}} — default: {{proposal}}

## 8. Verdict
- Actionable: {{yes/no — reason}}
- Risk: {{low|medium|high|critical}} — {{why}}
