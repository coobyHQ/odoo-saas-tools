from odoo import api, fields, models


class SaasPortalCreateClient(models.TransientModel):
    _name = 'saas_portal.create_client_inherit_support'
    _inherit = 'saas_portal.create_client'

    support_team_id = fields.Many2one(
        'saas_portal.support_team', 'Support Team',
        default=lambda self: self.env.user.support_team_id)
