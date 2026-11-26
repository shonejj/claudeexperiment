# Testing standards

- Each behaviour change has a test that fails without it. Bugs get a regression test first.
- Levels are reported explicitly: static, unit, integration, runtime (Odoo install/upgrade with tests),
  database, browser, production. Missing levels are listed, never implied.
- Odoo tests: `TransactionCase` by default, `HttpCase` for controllers/tours, `Form` for onchange, tagged
  `post_install`/`-at_install` when they need the full registry; no dependency on demo data.
- Runtime runs use disposable databases (`odoo-master runtime test`); `passed_no_tests` is a failure.
- Browser checks use throwaway credentials from `odoo-master runtime serve` or test accounts the user
  explicitly provided — never invented ones.
- Repair loops are bounded (workflow `max_loops`); after the bound, report the failure with evidence.
