# Copyright 2018 <Cooby tec>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class SaasPortalClient(models.Model):
    _inherit = 'saas_portal.client'

    ticket_ids = fields.One2many('website.support.ticket', 'saas_client_id', string='Support Tickets', readonly=False)
