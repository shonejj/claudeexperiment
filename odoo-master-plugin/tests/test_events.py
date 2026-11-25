import hashlib
import hmac
import json
import time

from odoo_master.integrations.events import handle_event, list_records, normalise
from conftest import FIXTURES


def _sig(secret, body):
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_jira_label_routes_and_dedupes(tmp_path, monkeypatch):
    monkeypatch.setenv("ODOO_MASTER_JIRA_WEBHOOK_SECRET", "s3cret")
    body = (FIXTURES / "events/jira_labeled.json").read_bytes()
    assert handle_event("jira", {}, body, tmp_path)["status"] == 401
    assert handle_event("jira", {"X-Hub-Signature": "sha256=deadbeef"}, body, tmp_path)["status"] == 401
    h = {"X-Hub-Signature": "sha256=" + _sig("s3cret", body)}
    r = handle_event("jira", h, body, tmp_path)
    assert r["status"] == 200 and r["results"][0]["workflow"] == "jira-ticket-planning"
    rec = list_records(tmp_path)[0]
    assert rec["inputs"] == {"ticket": "INV-42"} and rec["dispatch_mode"] == "record" and rec["command"][0] == "claude"
    assert handle_event("jira", h, body, tmp_path)["results"][0]["status"] == "duplicate"


def test_missing_secret_refuses(tmp_path):
    body = (FIXTURES / "events/jira_labeled.json").read_bytes()
    r = handle_event("jira", {"X-Hub-Signature": "sha256=x"}, body, tmp_path)
    assert r["status"] == 401 and "not set" in r["error"]


def test_slack_signature_challenge_and_route(tmp_path, monkeypatch):
    monkeypatch.setenv("ODOO_MASTER_SLACK_SIGNING_SECRET", "slk")
    ch = json.dumps({"type": "url_verification", "challenge": "abc"}).encode()
    ts = str(int(time.time()))
    def h(b, t=ts):
        return {"X-Slack-Request-Timestamp": t, "X-Slack-Signature": "v0=" + hmac.new(b"slk", f"v0:{t}:".encode() + b, hashlib.sha256).hexdigest()}
    assert handle_event("slack", h(ch), ch, tmp_path)["challenge"] == "abc"
    old = str(int(time.time()) - 3600)
    assert handle_event("slack", h(ch, old), ch, tmp_path)["status"] == 401   # replay window
    body = (FIXTURES / "events/slack_mention.json").read_bytes()
    r = handle_event("slack", h(body), body, tmp_path)
    assert r["results"][0]["workflow"] == "slack-issue-investigation"
    assert list_records(tmp_path)[0]["inputs"]["thread"] == "C123/1764100000.000100"


def test_github_signature_and_no_route(tmp_path, monkeypatch):
    monkeypatch.setenv("ODOO_MASTER_GITHUB_WEBHOOK_SECRET", "gh")
    body = json.dumps({"action": "labeled", "label": {"name": "odoo-master"}, "issue": {"number": 7},
                       "repository": {"full_name": "acme/erp"}}).encode()
    hdr = {"X-GitHub-Event": "issues", "X-GitHub-Delivery": "d-1", "X-Hub-Signature-256": "sha256=" + _sig("gh", body)}
    r = handle_event("github", hdr, body, tmp_path)
    assert r["results"][0]["workflow"] == "github-issue-development"
    assert list_records(tmp_path)[0]["inputs"]["issue"] == "acme/erp#7"
    body2 = json.dumps({"action": "labeled", "label": {"name": "other"}, "issue": {"number": 8}, "repository": {"full_name": "acme/erp"}}).encode()
    hdr2 = {"X-GitHub-Event": "issues", "X-GitHub-Delivery": "d-2", "X-Hub-Signature-256": "sha256=" + _sig("gh", body2)}
    assert handle_event("github", hdr2, body2, tmp_path)["results"][0]["status"] == "no_route"


def test_normalise_jira_status_and_assignee():
    p = {"webhookEvent": "jira:issue_updated", "issue": {"key": "A-1", "fields": {}},
         "changelog": {"items": [{"field": "status", "fromString": "To Do", "toString": "In Progress"},
                                 {"field": "assignee", "toString": "odoo-master-bot"}]}}
    types = [e["type"] for e in normalise("jira", {}, p)]
    assert types == ["jira.issue.status_changed", "jira.issue.assigned"]


def test_unknown_source(tmp_path):
    assert handle_event("nope", {}, b"{}", tmp_path)["status"] == 404
