"""Webhook event receiver and router.

MCP gives agents *tools*; it does not push events. Background triggers therefore arrive here as real
webhooks (GitHub, Slack Events API, Jira/Jira Automation, Linear) or from a scheduler, and are:

  1. authenticated   (HMAC signature with a secret from the environment; Slack v0 + timestamp window)
  2. normalised      (provider payload -> {type: "jira.issue.labeled", ...})
  3. deduplicated    (delivery id / content hash in a sqlite store)
  4. routed          (integrations/events/routes.yaml or .odoo-master/events/routes.yaml)
  5. recorded        (.odoo-master/events/records/<id>.json — the execution request)
  6. dispatched      (mode "record": store the exact command; mode "execute": run `claude -p ...`)

The receiver binds to 127.0.0.1 by default; expose it through your own reverse proxy / tunnel with TLS.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..util import PLUGIN_ROOT, load_yaml, now_iso, read_json, state_dir, write_json

MAX_BODY = 2 * 1024 * 1024
SLACK_TOLERANCE = 300


# ----------------------------------------------------------------------- config
def load_routes(root: Path | None = None) -> dict:
    proj = state_dir(root, create=False) / "events" / "routes.yaml"
    path = proj if proj.exists() else PLUGIN_ROOT / "integrations" / "events" / "routes.yaml"
    data = load_yaml(path)
    data["_source"] = str(path)
    return data


# ----------------------------------------------------------------------- auth
def verify(source: str, cfg: dict, headers: dict, body: bytes) -> tuple[bool, str]:
    h = {k.lower(): v for k, v in headers.items()}
    kind = cfg.get("signature", "none")
    if kind == "none":
        return True, "signature not required by configuration"
    secret = os.environ.get(cfg.get("secret_env", ""), "")
    if not secret:
        return False, f"secret env {cfg.get('secret_env')} not set — refusing unsigned events"
    if kind == "github":
        sig = h.get("x-hub-signature-256", "")
        exp = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, exp), "github signature"
    if kind == "slack":
        ts = h.get("x-slack-request-timestamp", "0")
        try:
            if abs(time.time() - int(ts)) > SLACK_TOLERANCE:
                return False, "slack timestamp outside tolerance (replay?)"
        except ValueError:
            return False, "bad slack timestamp"
        base = f"v0:{ts}:".encode() + body
        exp = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
        return hmac.compare_digest(h.get("x-slack-signature", ""), exp), "slack signature"
    if kind == "hmac-sha256":
        sig = h.get(cfg.get("header", "x-signature").lower(), "")
        digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig.removeprefix("sha256="), digest), "hmac-sha256 signature"
    return False, f"unknown signature kind {kind}"


# ----------------------------------------------------------------------- normalise
def normalise(source: str, headers: dict, payload: dict) -> list[dict]:
    """Return zero or more normalised events: {type, delivery_id, data...}."""
    h = {k.lower(): v for k, v in headers.items()}
    events = []
    if source == "github":
        ev = h.get("x-github-event", "")
        action = payload.get("action", "")
        base = {"delivery_id": h.get("x-github-delivery"), "repository": payload.get("repository", {}),
                "sender": (payload.get("sender") or {}).get("login")}
        if ev == "issues":
            label = (payload.get("label") or {}).get("name")
            events.append({**base, "type": f"github.issue.{ {'opened': 'created'}.get(action, action) }", "issue": payload.get("issue", {}), "label": label})
        elif ev == "pull_request":
            events.append({**base, "type": f"github.pull_request.{ {'synchronize': 'updated'}.get(action, action) }",
                           "pull_request": payload.get("pull_request", {})})
        elif ev in ("check_suite", "check_run") and action == "completed":
            events.append({**base, "type": "github.checks.completed", "check": payload.get(ev, {})})
        elif ev == "ping":
            events.append({**base, "type": "github.ping"})
    elif source == "slack":
        if payload.get("type") == "url_verification":
            return [{"type": "slack.url_verification", "challenge": payload.get("challenge")}]
        e = payload.get("event") or {}
        if e.get("type") in ("message", "app_mention") and not e.get("bot_id") and not e.get("subtype"):
            events.append({"type": "slack.message.received", "delivery_id": payload.get("event_id"), "channel": e.get("channel"),
                           "thread_ts": e.get("thread_ts") or e.get("ts"), "user": e.get("user"), "text": (e.get("text") or "")[:4000],
                           "mentions_bot": e.get("type") == "app_mention"})
    elif source == "jira":
        we = payload.get("webhookEvent", "")
        issue = payload.get("issue") or {}
        changes = ((payload.get("changelog") or {}).get("items")) or []
        fields = issue.get("fields") or {}
        base = {"issue": {"key": issue.get("key"), "id": issue.get("id"), "summary": fields.get("summary"),
                          "labels": fields.get("labels") or [], "status": (fields.get("status") or {}).get("name"),
                          "assignee": (fields.get("assignee") or {}).get("displayName") or (fields.get("assignee") or {}).get("accountId")},
                "user": (payload.get("user") or {}).get("displayName")}
        did = h.get("x-atlassian-webhook-identifier") or hashlib.sha256(
            json.dumps([we, issue.get("key"), payload.get("timestamp"), changes], sort_keys=True).encode()).hexdigest()[:24]
        if we == "jira:issue_created":
            events.append({**base, "type": "jira.issue.created", "delivery_id": did})
        elif we == "jira:issue_updated":
            for ch in changes:
                f = ch.get("field")
                if f == "labels":
                    added = set((ch.get("toString") or "").split()) - set((ch.get("fromString") or "").split())
                    for lab in sorted(added):
                        events.append({**base, "type": "jira.issue.labeled", "label": lab, "delivery_id": f"{did}:{lab}"})
                elif f == "status":
                    events.append({**base, "type": "jira.issue.status_changed", "from": ch.get("fromString"), "to": ch.get("toString"),
                                   "delivery_id": f"{did}:status"})
                elif f == "assignee":
                    events.append({**base, "type": "jira.issue.assigned", "assignee": ch.get("toString"), "delivery_id": f"{did}:assignee"})
    elif source == "linear":
        data = payload.get("data") or {}
        typ = payload.get("type", "").lower()
        act = payload.get("action", "")
        if typ == "issue":
            events.append({"type": f"linear.issue.{ {'create': 'created', 'update': 'updated'}.get(act, act) }",
                           "delivery_id": h.get("linear-delivery") or payload.get("webhookId", "") + str(payload.get("createdAt")),
                           "issue": {"key": data.get("identifier"), "title": data.get("title"),
                                     "labels": [lab.get("name") for lab in data.get("labels", [])] if isinstance(data.get("labels"), list) else []}})
    return events


# ----------------------------------------------------------------------- routing
def _get(obj, dotted):
    cur = obj
    for p in dotted.split("."):
        if isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return None
    return cur


def _fmt(template: str, ev: dict) -> str:
    return re.sub(r"\{([\w.]+)\}", lambda m: str(_get(ev, m.group(1)) if _get(ev, m.group(1)) is not None else ""), template)


def match_routes(ev: dict, routes: dict) -> list[dict]:
    out = []
    for r in routes.get("routes", []):
        if r.get("enabled") is False or r["event"] != ev["type"]:
            continue
        ok = True
        for k, v in (r.get("match") or {}).items():
            actual = ev.get(k, _get(ev, k))
            if k == "label":
                labels = [ev.get("label")] + list((ev.get("issue") or {}).get("labels") or [])
                ok = v in labels if ev["type"].endswith("labeled") and ev.get("label") is None else ev.get("label") == v
            elif actual != v:
                ok = False
            if not ok:
                break
        if ok:
            out.append(r)
    return out


# ----------------------------------------------------------------------- dedupe + records
class Store:
    def __init__(self, root: Path):
        d = state_dir(root) / "events"
        d.mkdir(parents=True, exist_ok=True)
        self.dir = d
        self.db = sqlite3.connect(str(d / "deliveries.sqlite"), check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS seen (key TEXT PRIMARY KEY, at TEXT)")
        self.lock = threading.Lock()

    def first_time(self, key: str) -> bool:
        with self.lock:
            try:
                self.db.execute("INSERT INTO seen VALUES (?, ?)", (key, now_iso()))
                self.db.commit()
                return True
            except sqlite3.IntegrityError:
                return False


def _prompt(route: dict, inputs: dict, ev: dict) -> str:
    args = " ".join(f'-i {k}="{v}"' for k, v in inputs.items())
    return (f"/odoo-master:workflow-execution Start workflow `{route['workflow']}` for event {ev['type']} "
            f"(route {route['id']}): run `odoo-master workflow start {route['workflow']} {args}` and drive it. "
            f"Risk hint: {route.get('risk', 'medium')}. Respect approval gates; do not act on any other ticket.")


def handle_event(source: str, headers: dict, body: bytes, root: Path, store: Store | None = None, routes: dict | None = None) -> dict:
    routes = routes or load_routes(root)
    scfg = (routes.get("sources") or {}).get(source)
    if scfg is None:
        return {"status": 404, "error": f"unknown source {source}"}
    ok, why = verify(source, scfg, headers, body)
    if not ok:
        return {"status": 401, "error": why if "not set" in why or "timestamp" in why or "unknown" in why else f"{why} missing or invalid"}
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"status": 400, "error": "invalid JSON"}
    events = normalise(source, headers, payload)
    if events and events[0]["type"] == "slack.url_verification":
        return {"status": 200, "challenge": events[0]["challenge"]}
    store = store or Store(root)
    results = []
    for ev in events:
        key = f"{source}:{ev.get('delivery_id') or hashlib.sha256(body).hexdigest()}"
        if not store.first_time(key):
            results.append({"event": ev["type"], "status": "duplicate", "key": key})
            continue
        for route in match_routes(ev, routes):
            inputs = {k: _fmt(v, ev) for k, v in (route.get("inputs") or {}).items()}
            rid = time.strftime("%Y%m%d-%H%M%S") + "-" + hashlib.sha256((key + route["id"]).encode()).hexdigest()[:6]
            prompt = _prompt(route, inputs, ev)
            cmd = [c.replace("{prompt}", prompt) for c in (routes.get("dispatch") or {}).get("command", ["claude", "-p", "{prompt}"])]
            rec = {"id": rid, "received_at": now_iso(), "source": source, "event": ev["type"], "delivery_key": key,
                   "route": route["id"], "workflow": route["workflow"], "inputs": inputs, "risk": route.get("risk", "medium"),
                   "authenticated": why, "dispatch_mode": (routes.get("dispatch") or {}).get("mode", "record"), "command": cmd,
                   "status": "recorded", "event_summary": {k: v for k, v in ev.items() if k in ("type", "label", "from", "to", "assignee", "channel", "thread_ts")}}
            if rec["dispatch_mode"] == "execute":
                logf = store.dir / "records" / f"{rid}.log"
                logf.parent.mkdir(parents=True, exist_ok=True)
                proc = subprocess.Popen(cmd, cwd=str(root), stdout=logf.open("w"), stderr=subprocess.STDOUT)
                rec.update(status="dispatched", pid=proc.pid, log=str(logf))
            write_json(store.dir / "records" / f"{rid}.json", rec)
            results.append({"event": ev["type"], "status": rec["status"], "record": rid, "workflow": route["workflow"]})
        if not any(r.get("event") == ev["type"] and r.get("record") for r in results):
            results.append({"event": ev["type"], "status": "no_route"})
    return {"status": 200, "results": results}


def list_records(root: Path | None = None) -> list:
    d = state_dir(root) / "events" / "records"
    return [read_json(p) for p in sorted(d.glob("*.json"))] if d.exists() else []


def simulate(source: str, body: bytes, root: Path, headers: dict | None = None) -> dict:
    return handle_event(source, headers or {}, body, root)


def serve(root: Path, host: str = "127.0.0.1", port: int = 8787) -> None:
    routes = load_routes(root)
    store = Store(root)

    class H(BaseHTTPRequestHandler):
        def _send(self, code, obj):
            data = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/health":
                return self._send(200, {"ok": True, "routes": len(routes.get("routes", []))})
            self._send(404, {"error": "not found"})

        def do_POST(self):
            m = re.match(r"^/events/([a-z0-9_-]+)$", self.path)
            if not m:
                return self._send(404, {"error": "use POST /events/<source>"})
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                return self._send(413, {"error": "payload too large"})
            body = self.rfile.read(n)
            res = handle_event(m.group(1), dict(self.headers.items()), body, root, store, routes)
            if "challenge" in res:
                return self._send(200, {"challenge": res["challenge"]})
            self._send(res.pop("status"), res)

        def log_message(self, fmt, *args):
            pass

    srv = ThreadingHTTPServer((host, port), H)
    print(json.dumps({"listening": f"http://{host}:{port}", "routes": routes["_source"]}), flush=True)
    srv.serve_forever()
