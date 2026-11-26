# Odoo architecture guidance

- **Module boundaries**: one business capability per module; dependencies flow from specific to general;
  no cycles (the inventory reports cycles). Bridge modules for optional integrations between apps.
- **Extension over modification**: registry composition by `depends` order means your extension applies only if
  the defining module is a (transitive) dependency.
- **Data model**: prefer Many2one + One2many over Many2many with extra semantics (use an explicit model);
  store computed fields only when searched/grouped/reported; index foreign keys used in domains.
- **Multi-company**: `company_id` + `_check_company_auto` + `check_company=True`; record rules with `company_ids`.
- **Business flows**: hook into state transitions via the standard methods (`action_confirm`,
  `button_validate`, `_post`, `_action_done`) and their `_prepare_*` helpers; keep side effects idempotent.
- **Integrations**: isolate connectors in their own module; configuration in settings + `ir.config_parameter`;
  async work in crons/queue with batch commits.
- **Frontend**: registries and `patch()`; assets per bundle; no global monkey patches.
- **Upgrade-friendliness**: avoid `replace` XPath on standard views, avoid copying standard templates, avoid
  private methods of standard code when a public/prepare hook exists; this keeps the next migration small.
