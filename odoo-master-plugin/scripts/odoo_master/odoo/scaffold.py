"""Version-correct module scaffolding for Odoo 16.0-20.0.

Unlike `odoo-bin scaffold` (one generic template), the generated module follows the target series:
  - hooks signature (cr/registry on 16, env on 17+)
  - view syntax (<tree>/view_mode tree on <=17, <list> on 18+; no attrs on 17+)
  - constraints (_sql_constraints on <=18, models.Constraint on 19+)
  - security (ir.model.access.csv on <=19, ir.access.csv on 20+; res.groups category vs privilege)
  - tests that create their own data (demo data is not loaded by default from 19.0)
The scaffold refuses to overwrite an existing directory.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..util import version_tuple

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,62}$")
MODEL_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")


def _title(s: str) -> str:
    return " ".join(w.capitalize() for w in re.split(r"[._]", s) if w)


def _class(model: str) -> str:
    return "".join(w.capitalize() for w in re.split(r"[._]", model) if w)


def render(name: str, series: str, model: str | None = None, depends: list[str] | None = None, title: str | None = None,
           license: str = "LGPL-3", author: str | None = None, with_tests: bool = True) -> dict[str, str]:
    if not NAME_RE.match(name):
        raise ValueError("module name must be snake_case (a-z, 0-9, _), 2-63 chars")
    v = version_tuple(series)
    if v < (16,) or v > (99,):
        raise ValueError("series must be 16.0 or newer")
    model = model or name.replace("_", ".", 1) if "_" in name else (model or f"x.{name}")
    if not MODEL_RE.match(model):
        raise ValueError("model must look like 'module.thing'")
    depends = depends or ["base"]
    title = title or _title(name)
    table = model.replace(".", "_")
    cls = _class(model)
    list_tag = "list" if v >= (18,) else "tree"
    view_mode = "list,form" if v >= (18,) else "tree,form"
    files: dict[str, str] = {}
    data = ["security/security.xml"]
    data.append("security/ir.access.csv" if v >= (20,) else "security/ir.model.access.csv")
    data += [f"views/{table}_views.xml", "views/menus.xml"]
    files["__manifest__.py"] = (
        "{\n"
        f'    "name": "{title}",\n'
        f'    "version": "{series}.1.0.0",\n'
        f'    "summary": "{title}",\n'
        f'    "license": "{license}",\n'
        + (f'    "author": "{author}",\n' if author else "")
        + f'    "depends": {depends!r},\n'.replace("'", '"')
        + '    "data": [\n' + "".join(f'        "{d}",\n' for d in data) + "    ],\n"
        '    "installable": True,\n'
        '    "application": False,\n'
        "}\n")
    files["__init__.py"] = "from . import models\n"
    files["models/__init__.py"] = f"from . import {table}\n"
    if v >= (19,):
        constraint = '    _name_uniq = models.Constraint("UNIQUE(name)", "The name must be unique.")\n'
    else:
        constraint = '    _sql_constraints = [\n        ("name_uniq", "unique(name)", "The name must be unique."),\n    ]\n'
    files[f"models/{table}.py"] = (
        "from odoo import api, fields, models\n"
        "from odoo.exceptions import ValidationError\n\n\n"
        f"class {cls}(models.Model):\n"
        f'    _name = "{model}"\n'
        f'    _description = "{title}"\n'
        '    _order = "name"\n\n'
        "    name = fields.Char(required=True)\n"
        "    active = fields.Boolean(default=True)\n"
        '    state = fields.Selection([("draft", "Draft"), ("done", "Done")], default="draft", required=True)\n'
        "    note = fields.Text()\n"
        '    line_count = fields.Integer(compute="_compute_line_count")\n\n'
        f"{constraint}\n"
        '    @api.depends("note")\n'
        "    def _compute_line_count(self):\n"
        "        for rec in self:\n"
        "            rec.line_count = len((rec.note or \"\").splitlines())\n\n"
        '    @api.constrains("name")\n'
        "    def _check_name(self):\n"
        "        for rec in self:\n"
        "            if rec.name and not rec.name.strip():\n"
        '                raise ValidationError("The name cannot be blank.")\n\n'
        "    def action_done(self):\n"
        '        self.write({"state": "done"})\n')
    # security: groups
    cat = "base.module_category_hidden"
    if v >= (19,):
        files["security/security.xml"] = (
            '<?xml version="1.0" encoding="utf-8"?>\n<odoo>\n'
            f'    <record id="privilege_{name}" model="res.groups.privilege">\n'
            f'        <field name="name">{title}</field>\n'
            "    </record>\n"
            f'    <record id="group_{name}_user" model="res.groups">\n'
            '        <field name="name">User</field>\n'
            f'        <field name="privilege_id" ref="privilege_{name}"/>\n'
            '        <field name="implied_ids" eval="[(4, ref(\'base.group_user\'))]"/>\n'
            "    </record>\n"
            f'    <record id="group_{name}_manager" model="res.groups">\n'
            '        <field name="name">Manager</field>\n'
            f'        <field name="privilege_id" ref="privilege_{name}"/>\n'
            f'        <field name="implied_ids" eval="[(4, ref(\'group_{name}_user\'))]"/>\n'
            "    </record>\n</odoo>\n")
    else:
        files["security/security.xml"] = (
            '<?xml version="1.0" encoding="utf-8"?>\n<odoo>\n'
            f'    <record id="group_{name}_user" model="res.groups">\n'
            f'        <field name="name">{title} / User</field>\n'
            f'        <field name="category_id" ref="{cat}"/>\n'
            '        <field name="implied_ids" eval="[(4, ref(\'base.group_user\'))]"/>\n'
            "    </record>\n"
            f'    <record id="group_{name}_manager" model="res.groups">\n'
            f'        <field name="name">{title} / Manager</field>\n'
            f'        <field name="category_id" ref="{cat}"/>\n'
            f'        <field name="implied_ids" eval="[(4, ref(\'group_{name}_user\'))]"/>\n'
            "    </record>\n</odoo>\n")
    if v >= (20,):
        files["security/ir.access.csv"] = (
            "id,name,model_id,group_id/id,operation,domain\n"
            f"access_{table}_user,{model} user,{model},group_{name}_user,cru,\n"
            f"access_{table}_manager,{model} manager,{model},group_{name}_manager,crud,\n")
    else:
        files["security/ir.model.access.csv"] = (
            "id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\n"
            f"access_{table}_user,{model} user,model_{table},group_{name}_user,1,1,1,0\n"
            f"access_{table}_manager,{model} manager,model_{table},group_{name}_manager,1,1,1,1\n")
    if v >= (17,):
        btn = '<button name="action_done" type="object" string="Mark done" class="btn-primary" invisible="state != \'draft\'"/>'
        readonly = ' readonly="state == \'done\'"'
    else:
        btn = '<button name="action_done" type="object" string="Mark done" class="btn-primary" attrs="{\'invisible\': [(\'state\', \'!=\', \'draft\')]}"/>'
        readonly = " attrs=\"{'readonly': [('state', '=', 'done')]}\""
    files[f"views/{table}_views.xml"] = (
        '<?xml version="1.0" encoding="utf-8"?>\n<odoo>\n'
        f'    <record id="{table}_view_{list_tag}" model="ir.ui.view">\n'
        f'        <field name="name">{model}.{list_tag}</field>\n'
        f'        <field name="model">{model}</field>\n'
        '        <field name="arch" type="xml">\n'
        f"            <{list_tag}>\n"
        '                <field name="name"/>\n'
        '                <field name="state"/>\n'
        f"            </{list_tag}>\n"
        "        </field>\n    </record>\n"
        f'    <record id="{table}_view_form" model="ir.ui.view">\n'
        f'        <field name="name">{model}.form</field>\n'
        f'        <field name="model">{model}</field>\n'
        '        <field name="arch" type="xml">\n'
        "            <form>\n"
        "                <header>\n"
        f"                    {btn}\n"
        '                    <field name="state" widget="statusbar"/>\n'
        "                </header>\n"
        "                <sheet>\n"
        "                    <group>\n"
        f'                        <field name="name"{readonly}/>\n'
        '                        <field name="note"/>\n'
        '                        <field name="line_count"/>\n'
        '                        <field name="active" invisible="1"/>\n'
        "                    </group>\n"
        "                </sheet>\n"
        "            </form>\n"
        "        </field>\n    </record>\n"
        f'    <record id="{table}_view_search" model="ir.ui.view">\n'
        f'        <field name="name">{model}.search</field>\n'
        f'        <field name="model">{model}</field>\n'
        '        <field name="arch" type="xml">\n'
        "            <search>\n"
        '                <field name="name"/>\n'
        '                <filter name="draft" string="Draft" domain="[(\'state\', \'=\', \'draft\')]"/>\n'
        '                <filter name="archived" string="Archived" domain="[(\'active\', \'=\', False)]"/>\n'
        "            </search>\n"
        "        </field>\n    </record>\n"
        f'    <record id="{table}_action" model="ir.actions.act_window">\n'
        f'        <field name="name">{title}</field>\n'
        f'        <field name="res_model">{model}</field>\n'
        f'        <field name="view_mode">{view_mode}</field>\n'
        "    </record>\n</odoo>\n")
    files["views/menus.xml"] = (
        '<?xml version="1.0" encoding="utf-8"?>\n<odoo>\n'
        f'    <menuitem id="{name}_menu_root" name="{title}" sequence="90" groups="group_{name}_user"/>\n'
        f'    <menuitem id="{table}_menu" name="{title}" parent="{name}_menu_root" action="{table}_action" sequence="10"/>\n'
        "</odoo>\n")
    if with_tests:
        groups_field = "group_ids" if v >= (19,) else "groups_id"
        files["tests/__init__.py"] = f"from . import test_{table}\n"
        files[f"tests/test_{table}.py"] = (
            "from odoo.exceptions import ValidationError\n"
            "from odoo.tests import TransactionCase, tagged\n\n\n"
            '@tagged("post_install", "-at_install")\n'
            f"class Test{cls}(TransactionCase):\n\n"
            "    @classmethod\n"
            "    def setUpClass(cls):\n"
            "        super().setUpClass()\n"
            '        cls.user = cls.env["res.users"].create({\n'
            f'            "name": "{title} user", "login": "{name}_test_user",\n'
            f'            "{groups_field}": [(6, 0, [cls.env.ref("{name}.group_{name}_user").id])],\n'
            "        })\n\n"
            "    def test_user_can_create_and_complete(self):\n"
            f'        rec = self.env["{model}"].with_user(self.user).create({{"name": "First", "note": "a\\nb"}})\n'
            '        self.assertEqual(rec.state, "draft")\n'
            "        self.assertEqual(rec.line_count, 2)\n"
            "        rec.action_done()\n"
            '        self.assertEqual(rec.state, "done")\n\n'
            "    def test_blank_name_rejected(self):\n"
            "        with self.assertRaises(ValidationError):\n"
            f'            self.env["{model}"].create({{"name": "   "}})\n')
    return files


def write(target_dir: Path, name: str, series: str, **kw) -> dict:
    target = Path(target_dir) / name
    if target.exists():
        raise FileExistsError(f"{target} already exists — the scaffold never overwrites")
    files = render(name, series, **kw)
    for rel, content in files.items():
        p = target / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return {"module": name, "series": series, "path": str(target), "files": sorted(files)}
