import json

import pytest

from odoo_master.reporting import evidence, render
from odoo_master.reporting.markdown import split_frontmatter, to_html

MD = """---
title: Plan
kind: implementation-plan
ticket: INV-42
---
# Plan

Text with **bold**, `code` and [a link](https://example.com).

| A | B |
|---|---|
| 1 | 2 |

- one
  - nested
1. first

```mermaid
flowchart LR
  A --> B
```

db_password = hunter2
"""


def test_markdown_conversion():
    fm, body = split_frontmatter(MD)
    assert fm["ticket"] == "INV-42"
    h = to_html(body)
    assert "<table>" in h and "<strong>bold</strong>" in h and '<pre class="mermaid">' in h and "<li>nested</li>" in h


def test_render_html_and_pdf(tmp_path):
    src = tmp_path / "plan.md"
    src.write_text(MD)
    res = render.render(src, ["html", "pdf"])
    html = (tmp_path / "plan.html").read_text()
    assert "hunter2" not in html and "REDACTED" in html
    pdf = next(o for o in res["outputs"] if o["format"] == "pdf")
    if not pdf["engine"]:
        pytest.skip(f"no PDF engine available: {pdf['attempts']}")
    assert pdf["ok"] and pdf["verify"]["ok"]
    assert (tmp_path / "plan.pdf").read_bytes()[:5] == b"%PDF-"


def test_verify_pdf_rejects_fake(tmp_path):
    fake = tmp_path / "x.pdf"
    fake.write_text("# not a pdf")
    assert render.verify_pdf(fake)["ok"] is False


def test_evidence_manifest_and_tamper(tmp_path):
    from odoo_master.workflow import engine
    (tmp_path / ".odoo-master/workflows").mkdir(parents=True)
    eid = engine.start("bug-fix", {"request": "x"}, tmp_path)["execution"]
    f = tmp_path / "validation.json"
    f.write_text(json.dumps({"passed": True}))
    evidence.add(eid, "validation", "static", str(f), tmp_path, status="passed")
    evidence.add(eid, "runtime-test", "runtime", None, tmp_path, status="skipped", summary="docker unavailable")
    m = evidence.manifest(eid, tmp_path)
    assert m["intent"] == "bug_fix"
    assert m["levels_achieved"] == ["static"] and m["levels_missing"] == ["runtime"] and m["complete"] is False
    assert evidence.verify(eid, tmp_path)["ok"]
    f.write_text("tampered")
    v = evidence.verify(eid, tmp_path)
    assert not v["ok"] and "hash mismatch" in v["problems"][0]["problem"]
    with pytest.raises(ValueError):
        evidence.add(eid, "nonsense", "static", None, tmp_path)
