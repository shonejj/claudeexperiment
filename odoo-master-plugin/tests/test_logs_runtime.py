from odoo_master.odoo.logs import summarize
from odoo_master.odoo import runtime

LOG = """2026-11-25 21:34:35,848 1 INFO db odoo.modules.loading: Loading module x (36/37)
2026-11-25 21:34:37,184 1 INFO db odoo.tests.stats: x: 4 tests 0.05s 43 queries
2026-11-25 21:34:37,184 1 INFO db odoo.tests.result: 1 failed, 0 error(s) of 2 tests when loading database 'db'
2026-11-25 21:34:37,200 1 ERROR db odoo.addons.x.tests.test_a: FAIL: TestA.test_b
Traceback (most recent call last):
  File "/mnt/addons/0/x/tests/test_a.py", line 10, in test_b
AssertionError: 1 != 2
2026-11-25 21:34:38,000 1 WARNING db odoo.models: x.y: no access rules
2026-11-25 21:34:38,100 1 ERROR db odoo.sql_db: bad query: ERROR:  column "foo" does not exist
"""


def test_summarize_log():
    s = summarize(LOG)
    assert s["tests"]["ran"] == 2 and s["tests"]["failed"] == 1
    assert not s["clean"] and s["levels"]["ERROR"] == 2 and len(s["tracebacks"]) == 1
    assert s["postgres_errors"]


def test_runtime_skips_without_docker(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "available", lambda: {"available": False, "reason": "docker CLI not installed"})
    r = runtime.test([str(tmp_path)], ["x"], "18.0", project_root=tmp_path)
    assert r["status"] == "skipped" and r["level"] == "runtime"
