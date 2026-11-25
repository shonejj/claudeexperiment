---
name: odoo-report-development
description: "Odoo QWeb reports and documents: ir.actions.report, QWeb templates with external_layout, paper formats, report inheritance, wkhtmltopdf constraints, and testing rendered output. Use for PDF/HTML reports inside Odoo."
---

# Odoo report development

```xml
<record id="action_report_quality_check" model="ir.actions.report">
    <field name="name">Quality Check</field>
    <field name="model">stock.quality.check</field>
    <field name="report_type">qweb-pdf</field>
    <field name="report_name">stock_quality_check.report_quality_check</field>
    <field name="binding_model_id" ref="model_stock_quality_check"/>
</record>
<template id="report_quality_check">
    <t t-call="web.html_container">
        <t t-foreach="docs" t-as="doc">
            <t t-call="web.external_layout">
                <div class="page"><h2 t-out="doc.name"/></div>
            </t>
        </t>
    </t>
</template>
```
- Use `t-out` (escaped) — `t-raw` is gone; `t-esc` still works.
- Extend standard reports by inheriting their template (`inherit_id="sale.report_saleorder_document"`) with XPath.
- Custom data: `AbstractModel` named `report.<module>.<report_name>` with `_get_report_values(self, docids, data=None)`.
- wkhtmltopdf 0.12.6 (patched Qt) is required for headers/footers; reporting engines are being modularised in SaaS 19.4+ — check the target series.
- Test: render in a runtime (`self.env.ref('...')._render_qweb_pdf(...)`, signature differs by version) or HttpCase download.
