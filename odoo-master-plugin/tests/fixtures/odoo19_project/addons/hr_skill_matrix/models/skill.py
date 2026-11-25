from odoo import fields, models


class HrSkillLevel(models.Model):
    _name = "hr.skill.matrix.level"
    _description = "Skill level"

    name = fields.Char(required=True)
    employee_id = fields.Many2one("hr.employee", required=True)

    _name_employee_uniq = models.Constraint("UNIQUE(name, employee_id)", "Level must be unique per employee.")
