"""Plugin integrity: every referenced component exists and has a consumer."""
import json
import re
import shutil
import subprocess

import pytest
import yaml

from conftest import PLUGIN


def fm(path):
    t = path.read_text()
    assert t.startswith("---\n"), path
    return yaml.safe_load(t.split("---")[1])


def test_agents_frontmatter_and_skills_exist():
    agents = list((PLUGIN / "agents").glob("*.md"))
    assert len(agents) == 25
    for a in agents:
        d = fm(a)
        assert d["name"] == a.stem and len(d["description"]) > 40
        for s in d.get("skills", []):
            assert (PLUGIN / "skills" / s / "SKILL.md").exists(), (a.name, s)


def test_skills_frontmatter():
    skills = list((PLUGIN / "skills").glob("*/SKILL.md"))
    assert len(skills) >= 33
    for s in skills:
        d = fm(s)
        assert d["name"] == s.parent.name and len(d["description"]) <= 1536


def test_workflow_agents_skills_capabilities_exist():
    tax = yaml.safe_load((PLUGIN / "integrations/mcp/capability-taxonomy.yaml").read_text())["capabilities"]
    for w in (PLUGIN / "workflows").glob("*.yaml"):
        d = yaml.safe_load(w.read_text())
        for s in d["steps"]:
            if s.get("capability"):
                assert s["capability"] in tax, (w.name, s["capability"])


def test_hooks_json_targets_exist():
    hooks = json.loads((PLUGIN / "hooks/hooks.json").read_text())["hooks"]
    src = (PLUGIN / "scripts/hook.py").read_text()
    for groups in hooks.values():
        for g in groups:
            for h in g["hooks"]:
                name = re.search(r'hook\.py" ([\w-]+)', h["command"]).group(1)
                assert f'"{name}"' in src


def test_templates_and_instructions_referenced():
    text = "".join(p.read_text() for p in list((PLUGIN / "skills").rglob("*.md")) + list((PLUGIN / "agents").glob("*.md")) + list((PLUGIN / "workflows").glob("*.yaml")))
    for t in (PLUGIN / "templates").rglob("*.*"):
        assert t.name in text or t.parent.name in text, f"unused template {t}"
    for i in (PLUGIN / "instructions").glob("*.md"):
        refs = text + (PLUGIN / "instructions/global.md").read_text() + (PLUGIN / "instructions/odoo-development.md").read_text()
        assert i.name in refs or i.stem in refs or i.name == "global.md", f"unreferenced instruction {i}"


def test_schemas_are_valid_jsonschema():
    import jsonschema
    for s in (PLUGIN / "schemas").glob("*.json"):
        jsonschema.Draft202012Validator.check_schema(json.loads(s.read_text()))


def test_routes_and_config_validate():
    from odoo_master.schemas import validate_file
    assert validate_file("event-routes", PLUGIN / "integrations/events/routes.yaml")["valid"]
    assert validate_file("config", PLUGIN / "config/defaults.yaml")["valid"]


@pytest.mark.skipif(not shutil.which("claude"), reason="claude CLI not installed")
def test_claude_plugin_validate():
    for target in (PLUGIN, PLUGIN.parent):
        r = subprocess.run(["claude", "plugin", "validate", str(target)], capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stdout + r.stderr
