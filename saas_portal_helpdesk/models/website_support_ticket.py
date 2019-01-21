from odoo import api, fields, models

import logging
_logger = logging.getLogger(__name__)


class WebsiteSupportTicket(models.Model):
    _inherit = "website.support.ticket"

    saas_client_id = fields.Many2one('saas_portal.client', string='SaaS Client Instance')

