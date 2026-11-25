"""Ephemeral Odoo runtime in Docker for install/upgrade tests and visual QA.

Only throwaway databases are created (prefix ``om_test_``); this module refuses to connect to any
existing database. Containers and networks are labelled ``odoo-master=1`` and removed afterwards
unless ``keep=True``.

  test(...)  -> install modules (+ optional upgrade pass) with --test-tags, collect and summarise the log
  serve(...) -> start an Odoo server with a fresh database for browser checks; returns URL + generated
                credentials of that throwaway database (stored under .odoo-master/session/, git-ignored)
  stop(id)   -> remove everything started by serve()
"""
from __future__ import annotations

import secrets
import shutil
import subprocess
import time
from pathlib import Path

from .logs import summarize
from ..util import now_iso, redact_text, state_dir, write_json, read_json

LABEL = "odoo-master=1"


def _docker(*args, timeout=600, check=False) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, check=check)


def available() -> dict:
    if not shutil.which("docker"):
        return {"available": False, "reason": "docker CLI not installed"}
    r = _docker("info", "--format", "{{.ServerVersion}}", timeout=30)
    if r.returncode != 0:
        return {"available": False, "reason": "docker daemon not reachable: " + r.stderr.strip()[:200]}
    return {"available": True, "server_version": r.stdout.strip()}


def _start_postgres(run_id: str, pg_image: str, network: str, password: str) -> str:
    name = f"om-pg-{run_id}"
    r = _docker("run", "-d", "--rm", "--name", name, "--label", LABEL, "--network", network,
                "-e", "POSTGRES_USER=odoo", "-e", f"POSTGRES_PASSWORD={password}", "-e", "POSTGRES_DB=postgres", pg_image)
    if r.returncode != 0:
        raise RuntimeError("postgres container failed: " + r.stderr[-500:])
    for _ in range(60):
        if _docker("exec", name, "pg_isready", "-U", "odoo", timeout=20).returncode == 0:
            time.sleep(1)
            return name
        time.sleep(1)
    raise RuntimeError("postgres did not become ready in 60s")


def _db_env(pg: str, password: str) -> list[str]:
    """The official image's entrypoint builds --db_host/--db_user/--db_password from HOST/USER/PASSWORD."""
    return ["-e", f"HOST={pg}", "-e", "PORT=5432", "-e", "USER=odoo", "-e", f"PASSWORD={password}"]


def _mounts(addons: list[str], enterprise: str | None) -> tuple[list[str], str]:
    args, paths = [], []
    for i, a in enumerate(addons):
        p = Path(a).resolve()
        args += ["-v", f"{p}:/mnt/addons/{i}:ro"]
        paths.append(f"/mnt/addons/{i}")
    if enterprise:
        args += ["-v", f"{Path(enterprise).resolve()}:/mnt/enterprise:ro"]
        paths.insert(0, "/mnt/enterprise")
    return args, ",".join(paths)


def _cleanup(run_id: str):
    _docker("rm", "-f", f"om-odoo-{run_id}", f"om-pg-{run_id}", timeout=60)
    _docker("network", "rm", f"om-net-{run_id}", timeout=60)


def test(addons: list[str], modules: list[str], series: str, image: str | None = None, pg_image: str = "postgres:16",
         enterprise: str | None = None, upgrade: bool = True, test_tags: str | None = None, keep: bool = False,
         extra_args: list[str] | None = None, project_root: Path | None = None, timeout: int = 3600) -> dict:
    av = available()
    if not av["available"]:
        return {"status": "skipped", "level": "runtime", "reason": av["reason"]}
    run_id = secrets.token_hex(4)
    image = image or f"odoo:{series}"
    network = f"om-net-{run_id}"
    password = secrets.token_urlsafe(16)
    db = f"om_test_{run_id}"
    logs_dir = state_dir(project_root) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    record = {"run_id": run_id, "started_at": now_iso(), "image": image, "pg_image": pg_image, "database": db,
              "modules": modules, "series": series, "level": "runtime", "passes": []}
    _docker("network", "create", "--label", LABEL, network, timeout=60)
    try:
        pg = _start_postgres(run_id, pg_image, network, password)
        mount_args, addons_path = _mounts(addons, enterprise)
        tags = test_tags or ",".join(f"/{m}" for m in modules)
        passes = [("install", ["-i", ",".join(modules)])]
        if upgrade:
            passes.append(("upgrade", ["-u", ",".join(modules)]))
        for label, mode in passes:
            cmd = ["run", "--rm", "--name", f"om-odoo-{run_id}", "--label", LABEL, "--network", network, *mount_args,
                   *_db_env(pg, password), image, "odoo", "--addons-path", addons_path, "-d", db, *mode, "--test-tags", tags, "--stop-after-init",
                   "--log-level", "test", *(extra_args or [])]
            t0 = time.time()
            r = _docker(*cmd, timeout=timeout)
            log = redact_text((r.stdout or "") + (r.stderr or "")).replace(password, "***")
            log_path = logs_dir / f"runtime-{run_id}-{label}.log"
            log_path.write_text(log, encoding="utf-8")
            summ = summarize(log)
            ran = summ["tests"].get("ran")
            failed = (summ["tests"].get("failed") or 0) + (summ["tests"].get("errors") or 0)
            status = "passed" if r.returncode == 0 and summ["clean"] and failed == 0 else "failed"
            if status == "passed" and not ran:
                status = "passed_no_tests"
            record["passes"].append({"pass": label, "exit_code": r.returncode, "seconds": round(time.time() - t0, 1),
                                     "status": status, "log": str(log_path), "summary": summ})
            if status == "failed":
                break
    except Exception as exc:  # noqa: BLE001 - record the failure as evidence
        record["error"] = str(exc)
    finally:
        if not keep:
            _cleanup(run_id)
    statuses = [p["status"] for p in record["passes"]]
    record["status"] = ("error" if record.get("error") else "failed" if "failed" in statuses or not statuses
                        else "passed_no_tests" if "passed_no_tests" in statuses else "passed")
    record["finished_at"] = now_iso()
    write_json(state_dir(project_root) / "evidence" / f"runtime-test-{run_id}.json", record)
    return record


def serve(addons: list[str], modules: list[str], series: str, image: str | None = None, pg_image: str = "postgres:16",
          enterprise: str | None = None, port: int = 8069, project_root: Path | None = None) -> dict:
    av = available()
    if not av["available"]:
        return {"status": "skipped", "reason": av["reason"]}
    run_id = secrets.token_hex(4)
    image = image or f"odoo:{series}"
    network, password, db = f"om-net-{run_id}", secrets.token_urlsafe(16), f"om_test_{run_id}"
    admin_pw = secrets.token_urlsafe(12)
    _docker("network", "create", "--label", LABEL, network, timeout=60)
    pg = _start_postgres(run_id, pg_image, network, password)
    mount_args, addons_path = _mounts(addons, enterprise)
    base = ["--addons-path", addons_path, "-d", db]
    env = _db_env(pg, password)
    init = _docker("run", "--rm", "--label", LABEL, "--network", network, *mount_args, *env, image, "odoo", *base,
                   "-i", ",".join(["base", *modules]), "--stop-after-init", timeout=1800)
    if init.returncode != 0:
        _cleanup(run_id)
        return {"status": "failed", "stage": "init", "log_tail": redact_text(init.stderr[-3000:])}
    # set the admin password of the throwaway database through the ORM (hashed), login: admin
    shell = subprocess.run(["docker", "run", "--rm", "-i", "--label", LABEL, "--network", network, *mount_args, *env, image,
                            "odoo", "shell", *base, "--no-http"],
                           input=f"u = env['res.users'].search([('login','=','admin')])\nu.password = {admin_pw!r}\nenv.cr.commit()\n",
                           capture_output=True, text=True, timeout=600)
    if shell.returncode != 0:
        _cleanup(run_id)
        return {"status": "failed", "stage": "set-password", "log_tail": redact_text(shell.stderr[-1500:]).replace(admin_pw, "***")}
    r = _docker("run", "-d", "--name", f"om-odoo-{run_id}", "--label", LABEL, "--network", network, "-p", f"{port}:8069",
                *mount_args, *env, image, "odoo", *base, "--db-filter", f"^{db}$", "--no-database-list")
    if r.returncode != 0:
        _cleanup(run_id)
        return {"status": "failed", "stage": "serve", "error": r.stderr[-800:]}
    url = f"http://localhost:{port}"
    for _ in range(90):
        h = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", f"{url}/web/login"], capture_output=True, text=True)
        if h.stdout.strip() == "200":
            break
        time.sleep(2)
    info = {"status": "running", "run_id": run_id, "url": url, "database": db, "login": "admin", "password": admin_pw,
            "note": "Credentials of a throwaway test database created by odoo-master; never reuse elsewhere."}
    write_json(state_dir(project_root) / "session" / f"runtime-{run_id}.json", info)
    return {k: v for k, v in info.items() if k != "password"} | {"credentials_file": str(state_dir(project_root) / "session" / f"runtime-{run_id}.json")}


def stop(run_id: str, project_root: Path | None = None) -> dict:
    _cleanup(run_id)
    f = state_dir(project_root) / "session" / f"runtime-{run_id}.json"
    if f.exists():
        f.unlink()
    return {"stopped": run_id}


def cleanup_all() -> dict:
    r = _docker("ps", "-aq", "--filter", f"label={LABEL}")
    ids = r.stdout.split()
    if ids:
        _docker("rm", "-f", *ids)
    n = _docker("network", "ls", "-q", "--filter", f"label={LABEL}").stdout.split()
    if n:
        _docker("network", "rm", *n)
    return {"removed_containers": len(ids), "removed_networks": len(n)}


def status(project_root: Path | None = None) -> list:
    d = state_dir(project_root) / "session"
    return [ {k: v for k, v in (read_json(p) or {}).items() if k != "password"} for p in sorted(d.glob("runtime-*.json"))] if d.exists() else []
