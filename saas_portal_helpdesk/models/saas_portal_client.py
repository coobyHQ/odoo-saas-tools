# Copyright 2018 <Cooby tec>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, api, models


class SaasPortalClient(models.Model):
    _inherit = 'saas_portal.client'

    @api.multi
    @api.depends('ticket_ids')
    def _get_number_of_open_tickets(self):
        for ticket in self:
            ticket.ticket_nr_open = len(ticket.ticket_ids)
            # Todo   ticket.ticket_nr_open = len(ticket.ticket_ids.filtered(lambda c: c.states.id <= 6))

    @api.multi
    @api.depends('ticket_ids')
    def _get_number_of_closed_tickets(self):
        for ticket in self:
            ticket.ticket_nr_open = len(ticket.ticket_ids)
            # ticket.ticket_nr_open = len(ticket.ticket_ids.filtered(lambda c: c.states.id >= 7))

    @api.multi
    def _get_number_of_tickets_text(self):
        for ticket in self:
            open_ticket = ticket.ticket_nr_open
            closed = ticket.ticket_nr_closed
            ticket.ticket_nr_text = "%s / %s" % (open_ticket, closed)

    ticket_ids = fields.One2many('website.support.ticket', 'saas_client_id', string='Support Tickets', readonly=False)
    ticket_nr_open = fields.Integer(string='# of open Tickets', compute=_get_number_of_open_tickets)
    ticket_nr_closed = fields.Integer(string='# of closed Tickets', compute=_get_number_of_closed_tickets)
    ticket_nr_text = fields.Char('# of Tickets', compute=_get_number_of_tickets_text)
    ticket_latest_id = fields.Many2one('website.support.ticket', string='Latest Ticket', readonly=True)
