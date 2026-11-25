"""Compress an Odoo server log into a small JSON summary (token economy).

Recognises the standard Odoo log line format:
  2026-11-25 21:13:12,205 1 INFO dbname odoo.modules.loading: message
and test result lines (odoo.tests.result / odoo.tests.stats), tracebacks and PostgreSQL errors.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

LINE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+) (\d+) (DEBUG|INFO|WARNING|ERROR|CRITICAL|TEST|RUNBOT) (\S+) ([\w.]+): (.*)$")
TESTS_RAN = re.compile(r"(\d+) failed, (\d+) error\(s\) of (\d+) tests")
TESTS_OK = re.compile(r"Ran (\d+) tests? in")
TESTS_STATS = re.compile(r"(\d+) post-tests? in|(\d+) tests? +[\d.]+s")
PG_ERR = re.compile(r"psycopg2?\.(errors\.)?\w+|ERROR:\s+(duplicate key|null value|column .* does not exist|relation .* does not exist|syntax error)")


def summarize(text: str, max_items: int = 30) -> dict:
    levels: Counter = Counter()
    errors, warnings, tracebacks, pg_errors = [], [], [], []
    loggers: Counter = Counter()
    tests = {"ran": None, "failed": None, "errors": None, "lines": []}
    tb: list[str] | None = None
    for raw in text.splitlines():
        m = LINE.match(raw)
        if m:
            if tb is not None:
                tracebacks.append("\n".join(tb[-12:]))
                tb = None
            _, _, level, db, logger, msg = m.groups()
            levels[level] += 1
            if level in ("ERROR", "CRITICAL"):
                loggers[logger] += 1
                if len(errors) < max_items:
                    errors.append({"logger": logger, "message": msg[:400]})
            elif level == "WARNING" and len(warnings) < max_items:
                warnings.append({"logger": logger, "message": msg[:300]})
            if logger.startswith("odoo.tests"):
                r = TESTS_RAN.search(msg)
                if r:
                    tests["failed"], tests["errors"], tests["ran"] = int(r.group(1)), int(r.group(2)), int(r.group(3))
                elif "tests" in msg and len(tests["lines"]) < 10:
                    tests["lines"].append(msg[:200])
                    s = TESTS_STATS.search(msg)
                    if s and tests["ran"] is None:
                        tests["ran_hint"] = msg[:200]
            r2 = TESTS_OK.search(msg)
            if r2:
                tests["ran"] = (tests["ran"] or 0) + int(r2.group(1))
            if PG_ERR.search(msg) and len(pg_errors) < max_items:
                pg_errors.append(msg[:300])
        else:
            if raw.startswith("Traceback (most recent call last)"):
                tb = [raw]
            elif tb is not None:
                tb.append(raw)
            if PG_ERR.search(raw) and len(pg_errors) < max_items:
                pg_errors.append(raw[:300])
    if tb is not None:
        tracebacks.append("\n".join(tb[-12:]))
    clean = levels["ERROR"] == 0 and levels["CRITICAL"] == 0 and not tracebacks
    return {"levels": dict(levels), "clean": clean, "errors": errors, "warnings": warnings[:15],
            "tracebacks": tracebacks[:10], "postgres_errors": pg_errors, "top_error_loggers": loggers.most_common(5),
            "tests": tests}


def summarize_file(path: Path | str) -> dict:
    return summarize(Path(path).read_text(encoding="utf-8", errors="ignore"))
