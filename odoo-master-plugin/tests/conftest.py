import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))
os.environ["CLAUDE_PLUGIN_ROOT"] = str(PLUGIN)
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    for k in list(os.environ):
        if k.startswith(("CLAUDE_PLUGIN_OPTION_", "ODOO_MASTER_")):
            monkeypatch.delenv(k, raising=False)


@pytest.fixture
def fx(tmp_path):
    """Copy a fixture repository into an isolated tmp dir and return its path."""
    def _copy(name):
        dst = tmp_path / name
        shutil.copytree(FIXTURES / name, dst, ignore=shutil.ignore_patterns(".odoo-master"))
        return dst
    return _copy


def run_hook(name, payload, cwd=None, env=None):
    p = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "hook.py"), name], input=json.dumps(payload),
                       capture_output=True, text=True, env={**os.environ, **(env or {})}, cwd=cwd, timeout=120)
    out = p.stdout.strip()
    try:
        return p.returncode, json.loads(out) if out.startswith("{") else out
    except json.JSONDecodeError:
        return p.returncode, out


def cli(*args, root=None):
    cmd = [str(PLUGIN / "bin" / "odoo-master")]
    if root:
        cmd += ["--root", str(root)]
    p = subprocess.run(cmd + list(args), capture_output=True, text=True, timeout=300)
    try:
        data = json.loads(p.stdout) if p.stdout.strip().startswith(("{", "[")) else p.stdout
    except json.JSONDecodeError:
        data = p.stdout
    return p.returncode, data, p.stderr
