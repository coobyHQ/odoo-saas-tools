# Copyright 2018 <Cooby tec>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, api, models


class SaasPortalClient(models.Model):
    _inherit = 'saas_portal.client'

    @api.multi
    @api.depends('ticket_ids', 'ticket_ids.state')
    def _get_number_of_tickets(self):
        closed_states = [
            self.env.ref('website_support.website_ticket_state_customer_closed', raise_if_not_found=False),
            self.env.ref('website_support.website_ticket_state_staff_closed', raise_if_not_found=False)
        ]
        for ticket in self:
            ticket.ticket_nr_open = len(ticket.ticket_ids.filtered(lambda c: c.state not in closed_states))
            ticket.ticket_nr_closed = len(ticket.ticket_ids.filtered(lambda c: c.state in closed_states))
            ticket.ticket_nr_text = "%s / %s" % (ticket.ticket_nr_open, ticket.ticket_nr_closed)

    def _get_string_of_tickets(self):
        open_t = self.ticket_nr_open
        closed = self.ticket_nr_closed
        self.ticket_nr_string = "%s/%s" % (open_t, closed)
        return

    ticket_ids = fields.One2many('website.support.ticket', 'saas_client_id', string='Support Tickets', readonly=False)
    ticket_nr_open = fields.Integer(string='# of open Tickets', compute=_get_number_of_tickets)
    ticket_nr_closed = fields.Integer(string='# of closed Tickets', compute=_get_number_of_tickets)
    ticket_nr_text = fields.Char('# of Tickets', compute=_get_number_of_tickets)
    ticket_latest_id = fields.Many2one('website.support.ticket', string='Latest Ticket', readonly=True)
    ticket_nr_string = fields.Char('# of Tickets', compute=_get_string_of_tickets)
    ticket_sla_id = fields.Many2one('website.support.sla', string='Service Level Agreement', readonly=True)

    @api.multi
    def action_show_open_tickets(self):
        closed_states = [
            self.env.ref('website_support.website_ticket_state_customer_closed', raise_if_not_found=False),
            self.env.ref('website_support.website_ticket_state_staff_closed', raise_if_not_found=False)
        ]
        tickets = self.ticket_ids.filtered(lambda c: c.state not in closed_states)
        action = self.env.ref('website_support.website_support_ticket_action_partner').read()[0]
        if tickets and action:
            action['views'] = [(self.env.ref('website_support.website_support_ticket_view_form').id, 'form')]
            action['res_id'] = tickets.sorted(lambda c: c.create_date)[-1].id
        else:
            action['views'] = [(self.env.ref('website_support.website_support_ticket_view_form').id, 'form')]
        return action

    @api.multi
    def action_show_sla(self):
        active_sla = "tobedone"
        action = self.env.ref('website_support.website_support_sla_action').read()[0]

        if self.ticket_sla_id and action:
            action['views'] = [(self.env.ref('website_support.website_support_sla_view_tree').id, 'tree'),
                               (self.env.ref('website_support.website_support_sla_view_form').id, 'form')]
            action['domain'] = [('id', '=', self.ticket_sla_id)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action