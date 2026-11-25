"""Minimal MCP client used for discovery only: initialize + tools/list over stdio or Streamable HTTP.

It never calls tools. Servers needing OAuth return `needs_auth`; those are discovered from inside the
Claude Code session instead (the session holds the tokens).
"""
from __future__ import annotations

import json
import os
import re
import select
import subprocess
import time
import urllib.error
import urllib.request

PROTOCOL_VERSION = "2025-06-18"
CLIENT_INFO = {"name": "odoo-master-discovery", "version": "0.1.0"}
_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def expand(value, env=None):
    """Claude Code style ${VAR} / ${VAR:-default} expansion."""
    env = env or os.environ
    if isinstance(value, str):
        return _VAR.sub(lambda m: env.get(m.group(1), m.group(2) if m.group(2) is not None else m.group(0)), value)
    if isinstance(value, list):
        return [expand(v, env) for v in value]
    if isinstance(value, dict):
        return {k: expand(v, env) for k, v in value.items()}
    return value


def _rpc(i, method, params=None):
    msg = {"jsonrpc": "2.0", "id": i, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


def probe_stdio(cfg: dict, timeout: int = 20) -> dict:
    cmd = [expand(cfg["command"]), *expand(cfg.get("args", []))]
    env = {**os.environ, **expand(cfg.get("env", {}))}
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, bufsize=1)
    except (FileNotFoundError, PermissionError) as exc:
        return {"status": "failed", "error": f"cannot start: {exc}"}
    deadline = time.time() + timeout

    def send(obj):
        proc.stdin.write(json.dumps(obj) + "\n")
        proc.stdin.flush()

    def recv(want_id):
        buf = ""
        while time.time() < deadline:
            r, _, _ = select.select([proc.stdout], [], [], max(0.05, deadline - time.time()))
            if not r:
                break
            line = proc.stdout.readline()
            if not line:
                break
            buf = line.strip()
            if not buf:
                continue
            try:
                msg = json.loads(buf)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == want_id:
                return msg
        return None
    try:
        send(_rpc(1, "initialize", {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": CLIENT_INFO}))
        init = recv(1)
        if not init or "error" in init:
            return {"status": "failed", "error": (init or {}).get("error") or "no initialize response",
                    "stderr": (proc.stderr.read(2000) if proc.poll() is not None else "")}
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        tools, cursor, i = [], None, 2
        while True:
            send(_rpc(i, "tools/list", {"cursor": cursor} if cursor else {}))
            res = recv(i)
            if not res or "error" in res:
                return {"status": "failed", "error": (res or {}).get("error") or "no tools/list response", "server": init.get("result", {}).get("serverInfo")}
            tools += res["result"].get("tools", [])
            cursor = res["result"].get("nextCursor")
            i += 1
            if not cursor:
                break
        r = init["result"]
        return {"status": "connected", "server": r.get("serverInfo"), "protocol": r.get("protocolVersion"),
                "capabilities": r.get("capabilities"), "tools": tools}
    finally:
        try:
            proc.kill()
        except Exception:
            pass


def _http_post(url, body, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        ctype = resp.headers.get("Content-Type", "")
        raw = resp.read().decode("utf-8", "replace")
        sid = resp.headers.get("Mcp-Session-Id")
    if "text/event-stream" in ctype:
        msgs = [json.loads(ln[5:].strip()) for ln in raw.splitlines() if ln.startswith("data:") and ln[5:].strip()]
        msg = next((m for m in msgs if m.get("id") == body.get("id")), msgs[-1] if msgs else {})
    else:
        msg = json.loads(raw) if raw.strip() else {}
    return msg, sid


def probe_http(cfg: dict, timeout: int = 20) -> dict:
    url = expand(cfg["url"])
    headers = expand(cfg.get("headers", {}))
    try:
        init, sid = _http_post(url, _rpc(1, "initialize", {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": CLIENT_INFO}), headers, timeout)
        if sid:
            headers["Mcp-Session-Id"] = sid
        headers["MCP-Protocol-Version"] = init.get("result", {}).get("protocolVersion", PROTOCOL_VERSION)
        try:
            _http_post(url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, headers, timeout)
        except Exception:
            pass
        tools, cursor, i = [], None, 2
        while True:
            res, _ = _http_post(url, _rpc(i, "tools/list", {"cursor": cursor} if cursor else {}), headers, timeout)
            if "error" in res:
                return {"status": "failed", "error": res["error"]}
            tools += res.get("result", {}).get("tools", [])
            cursor = res.get("result", {}).get("nextCursor")
            i += 1
            if not cursor:
                break
        return {"status": "connected", "server": init.get("result", {}).get("serverInfo"), "tools": tools}
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return {"status": "needs_auth", "error": f"HTTP {exc.code}: authenticate in Claude Code (/mcp); discover from the session"}
        return {"status": "failed", "error": f"HTTP {exc.code}"}
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {"status": "failed", "error": str(exc)[:300]}


def probe(cfg: dict, timeout: int = 20) -> dict:
    t = cfg.get("type") or ("stdio" if "command" in cfg else None)
    if t == "stdio":
        return probe_stdio(cfg, timeout)
    if t in ("http", "streamable-http", "sse"):
        if t == "sse":
            return {"status": "unknown", "error": "legacy SSE transport: discover from the Claude Code session"}
        return probe_http(cfg, timeout)
    return {"status": "unknown", "error": f"unsupported transport {t!r}"}
