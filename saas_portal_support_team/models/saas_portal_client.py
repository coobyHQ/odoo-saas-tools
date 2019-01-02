from odoo import fields, models

import logging
_logger = logging.getLogger(__name__)


class SaasPortalClient(models.Model):
    _name = 'saas_portal.client.support'
    _inherit = 'saas_portal.client'

    support_team_id = fields.Many2one(
        'saas_portal.support_team', 'Support Team')

