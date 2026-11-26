---
name: odoo-controller-development
description: "Odoo HTTP controllers: routes, type http/json/jsonrpc, auth user/public/none/bearer, CSRF, request.env, portal/website pages, JSON APIs and safe sudo usage. Use when adding endpoints, portal pages or webhooks inside Odoo."
---

# Odoo controllers

```python
from odoo import http
from odoo.http import request


class QualityApi(http.Controller):

    @http.route("/quality/checks", type="jsonrpc", auth="user", methods=["POST"])   # 19+: jsonrpc ; ≤18: json
    def checks(self, picking_id):
        picking = request.env["stock.picking"].browse(int(picking_id))
        picking.check_access("read")            # 18+; ≤17: check_access_rights + check_access_rule
        return picking.quality_check_ids.read(["name", "state"])

    @http.route("/quality/webhook", type="http", auth="none", methods=["POST"], csrf=False)
    def webhook(self, **kw):
        # verify an HMAC signature from a secret in ir.config_parameter BEFORE touching data
        ...
```
- `auth`: `user` (logged in), `public` (website visitors, public user), `none` (no db user; use for webhooks with signature verification), `bearer` (API keys, 18+ docs).
- CSRF is on for `type="http"` POST with sessions; disable only for signed machine-to-machine endpoints.
- `sudo()` in public routes: narrow to specific records/fields; never pass user-provided domains to a sudo search.
- Portal: inherit `portal.CustomerPortal`, `_prepare_home_portal_values`, record rules for portal users.
- Tests: `HttpCase.url_open` / `self.make_jsonrpc_request` (version-dependent helper) and authentication via `self.authenticate(login, password)` with users created in the test.
