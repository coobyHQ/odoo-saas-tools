from odoo import models, fields


class SaasPortalPlan(models.Model):
    _inherit = 'saas_portal.plan'

    on_create = fields.Selection(
        selection_add=[('email_credentials', 'Only send an e-mail (no auto login)')],
    )