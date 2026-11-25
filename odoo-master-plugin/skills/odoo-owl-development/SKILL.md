---
name: odoo-owl-development
description: "Odoo web client JavaScript with OWL: components, templates, hooks, services, registries (fields, views, actions, systray), patch(), asset bundles, JS tests (Hoot 18+, QUnit before), and OWL 3 changes in Odoo 20. Use for custom widgets, client actions and frontend behaviour."
---

# OWL development

```js
/** @odoo-module **/            // optional from 17 for files in static/src
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class QualityBadge extends Component {
    static template = "stock_quality_check.QualityBadge";
    static props = { ...standardFieldProps };
    setup() {
        this.notification = useService("notification");
        this.state = useState({ open: false });
    }
}
registry.category("fields").add("quality_badge", { component: QualityBadge });
```
```xml
<templates xml:space="preserve">
    <t t-name="stock_quality_check.QualityBadge">
        <span class="badge" t-att-class="props.record.data[props.name] === 'done' ? 'text-bg-success' : 'text-bg-warning'"
              t-esc="props.record.data[props.name]"/>
    </t>
</templates>
```
- Register files in `assets` → `web.assets_backend` (JS, XML, SCSS); tests in `web.assets_unit_tests` (18+, Hoot) or `web.qunit_suite_tests` (≤17); tours in `web.assets_tests`.
- Extend core components with `patch(Component.prototype, { setup() { super.setup(...arguments); ... } })` — never copy them.
- Field widget API changed between series (props, `extractProps`) — read the target version's `@web/views/fields/*` in the official image before writing.
- **Odoo 20 = OWL 3**: run `odoo-bin upgrade_code --from 19.0 --to 20.0 --dry-run` (owl3-migration script) and review every change.
- Validation here is syntax-only (`node --check`); real verification needs `runtime serve` + `visual-qa` or JS tests in a runtime.
