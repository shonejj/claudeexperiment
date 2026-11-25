# Odoo security standards

- Least privilege: ACL rows per group, never group-less unless intentionally global; portal/public explicit.
- Record rules: understand global (AND) vs group (OR) semantics; on 20.0 express restrictions as `ir.access`
  domains. Test with real non-admin users.
- `sudo()` only for a narrow purpose; never with user-provided domains/ids without explicit checks.
- Controllers: correct `auth`, CSRF on session POSTs, validate inputs, `check_access` on records by id.
- No `eval`/`exec` on data; `safe_eval` only for trusted admin input; `ast.literal_eval` for literals.
- SQL only parameterised. QWeb `t-out` (escaped).
- Secrets live in environment variables or `ir.config_parameter` restricted to system group — never in code,
  data files, logs, reports, ticket comments or chat.
- Personal/production data never leaves the system in reports unless the user explicitly approves it.
