from odoo import http
from odoo.http import request
from odoo.addons.saas_portal.controllers.main import SaasPortal


class SaasPortalStart(SaasPortal):

    @http.route(['/page/website.start', '/page/start'], type='http', auth="public", website=True)
    def start(self, **post):
        base_saas_domain = self.get_config_parameter('base_saas_domain')
        values = {
            'base_saas_domain': base_saas_domain,
            'plan_id': post.get('plan_id')
        }
        if post.get('plan_id', False):
            plan = request.env['saas_portal.plan'].sudo().browse(post.get('plan_id'))
            if plan and plan.server_id and plan.server_id.domain: values.update(base_saas_domain = plan.server_id.domain)
        return request.render("website.start", values)
