from odoo import models, fields, api
from datetime import datetime
from odoo.tools.misc import formatLang

class SaasPortalClient(models.Model):
    _inherit = 'saas_portal.client'

    contract_id = fields.Many2one('account.analytic.account', string='Contract', readonly=True)
    contract_line_ids = fields.One2many(related='contract_id.recurring_invoice_line_ids',
                                        string='Product invoice lines', readonly=True)
    topup_users = fields.Integer('Additional users', compute='_get_user_topup_sum', help='from Topups', readonly=True)
    topup_storage = fields.Integer('Additional storage (MB)',  compute='_get_storage_topup_sum',
                                         help='from Topups', readonly=True)
    saas_contract_state = fields.Char('Contract state', compute='_compute_contract_state',)

    # Get the sum of Topuped # of users
    @api.multi
    @api.depends('contract_line_ids.name', 'contract_line_ids.quantity')
    def _get_user_topup_sum(self):
        for users in self:
            sum_total = 0.0

            for line in users.contract_line_ids:
                if line.uom_id is 'Users':
                    sum_total += line.quantity
                    users.update({
                        'topup_users': sum_total
                    })

    # Get the sum of Topuped Nr. of storage
    # Todo adding logic for differnet UOM as GB
    @api.multi
    @api.depends('contract_line_ids.name', 'contract_line_ids.quantity')
    def _get_storage_topup_sum(self):
        for storage in self:
            sum_total = 0.0

            for line in storage.contract_line_ids:
                if line.uom_id is 'MB':
                    sum_total += line.quantity
                    storage.update({
                        'topup_storage': sum_total
                    })

    @api.multi
    def _compute_contract_state(self):
        for client in self:
            state = "paid"
            today = datetime.today().strftime('%Y-%m-%d')
            if client.contract_id:
                invoices = self.env['account.invoice'].search([('contract_id', '=', client.contract_id.id)])
                amount_due = 0
                for invoice in invoices:
                    if invoice.residual > 0 and invoice.state != 'draft' and today > invoice.date_due:
                        amount_due += invoice.residual
                if amount_due and invoice:
                    state = str(formatLang(self.env, amount_due, currency_obj=invoice.currency_id))
            client.saas_contract_state = state

    @api.multi
    def act_show_contract(self):
        contract = self.contract_id
        action = self.env.ref('contract.action_account_analytic_sale_overdue_all').read()[0]
        if action:
            action['views'] = [(self.env.ref('contract.account_analytic_account_sale_form').id, 'form')]
            action['res_id'] = contract.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action
