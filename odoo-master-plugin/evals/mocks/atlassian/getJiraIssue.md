---
expect:
  issueIdOrKey: string
---
{"key": "{{input.issueIdOrKey}}", "fields": {"summary": "Receipts can be validated while quality checks are still pending",
 "description": "Warehouse users report that some incoming receipts (WH/IN) get validated although a quality check is still in 'To Do'. Expected: validation is blocked until all checks are passed or failed. Odoo 18, module stock_quality_check.",
 "comment": {"comments": [{"author": {"displayName": "QA lead"}, "body": "Happens when the check is created after the picking is marked ready."}]},
 "status": {"name": "To Do"}, "labels": ["inventory", "odoo"]}}
