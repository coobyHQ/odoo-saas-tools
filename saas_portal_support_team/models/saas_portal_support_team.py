from odoo import fields, models

import logging
_logger = logging.getLogger(__name__)


class SaasPortalSupportTeams(models.Model):
    _name = 'saas_portal.support_team'

    _inherit = ['mail.thread']

    name = fields.Char('Team name')
    user_ids = fields.One2many('res.users', 'support_team_id', string='Users')
