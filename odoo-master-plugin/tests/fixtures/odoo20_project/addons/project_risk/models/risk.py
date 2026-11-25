from odoo import fields, models


class ProjectRisk(models.Model):
    _name = "project.risk"
    _description = "Project Risk"

    name = fields.Char(required=True)
    project_id = fields.Many2one("project.project", required=True)
    probability = fields.Selection([("low", "Low"), ("high", "High")], default="low")
