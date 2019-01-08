from odoo import api, exceptions, fields, models


class SaasPortalPlanTopup (models.Model):
    _name = 'saas_portal.plan_topup'
    _description = 'SaaS Plan Topups (addons)'

    name = fields.Char('Name', required=True)
    product_tmpl_id = fields.Many2one('product.template', 'Product Template', domain=[('saas_product_type', '=', 'topup')], required=True)
    plan_id = fields.Many2one('saas_portal.plan', string='Plan', required=True)
    contract_template_id = fields.Many2one('account.analytic.contract', string='Contract Template')
    topup_users = fields.Integer('# of Extra Users', default=1)
    topup_storage = fields.Integer('# of Extra Storage (MB)', default=0)
