from odoo import models, fields, api
from odoo.tools import scan_languages


class SaasPortalPlanAttribute(models.Model):
    _name = 'saas_portal.attribute'
    _description = 'SaaS Plan Topups (addons)'

    def _get_default_lang(self):
        return self.env.user.lang

    name = fields.Char('Name', required=True)
    plan_id = fields.Many2one('saas_portal.plan', 'Plan')

#    topup_ids = fields.One2many('saas_portal.plan_topup', inverse_name='plan_id', string='Top ups')

    product_attribute_id = fields.One2many(related='plan_id.attribute_line_ids',
                                           String='Product variant')
    template_id = fields.Many2one(
        'saas_portal.database', 'Template', ondelete='restrict')
    lang = fields.Selection(scan_languages(), 'Language', default=_get_default_lang)


