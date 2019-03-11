from odoo import api, fields, models

import logging
_logger = logging.getLogger(__name__)


class WebsiteSupportTicket(models.Model):
    _inherit = "website.support.ticket"

    saas_client_id = fields.Many2one('saas_portal.client', string='SaaS Client Instance')
    saas_client_ident = fields.Char(related='saas_client_id.identifier', string='Identifier')

    @api.multi
    def action_open_saas_client(self):
        saas_client = self.saas_client_id
        action = self.env.ref('saas_portal.action_clients').read()[0]
        if saas_client and action:
            action['views'] = [(self.env.ref('saas_portal.view_clients_form').id, 'form')]
            action['res_id'] = saas_client.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action


class WebsiteSupportSLA(models.Model):
    _inherit = "website.support.sla"

    saas_client_ids = fields.One2many('saas_portal.client', 'ticket_sla_id', string='SaaS Client Instances',
                                      readme='Connected SaaS instances')
