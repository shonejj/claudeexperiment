from odoo import http
from odoo.http import request


class SkillController(http.Controller):

    @http.route("/skills/levels", type="jsonrpc", auth="user")
    def levels(self):
        return request.env["hr.skill.matrix.level"].search_read([], ["name"])
