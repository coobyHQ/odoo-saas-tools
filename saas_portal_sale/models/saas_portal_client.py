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

    @api.multi
    @api.depends('contract_line_ids.product_id', 'contract_line_ids.quantity')
    def _get_user_topup_sum(self):
        for client in self:
            sum_total = 0.0
            users_uom = self.env.ref('saas_portal_sale.product_uom_users', raise_if_not_found=False)

            for line in client.contract_line_ids:
                if line.product_id and line.product_id.saas_product_type == 'topup' \
                        and line.product_id.saas_topup_type == 'users' and line.uom_id == users_uom:
                    sum_total += line.quantity
            client.topup_users = sum_total

    @api.multi
    @api.depends('contract_line_ids.product_id', 'contract_line_ids.quantity')
    def _get_storage_topup_sum(self):
        for client in self:
            sum_total = 0.0
            mb_uom = self.env.ref('saas_portal_sale.product_uom_megabyte', raise_if_not_found=False)
            uom_storage_category = self.env.ref('saas_portal_sale.product_uom_categ_storage', raise_if_not_found=False)

            for line in client.contract_line_ids:
                if line.product_id and line.product_id.saas_product_type == 'topup' \
                        and line.product_id.saas_topup_type == 'storage': # and line.uom_id == mb_uom:
                    if line.uom_id and line.uom_id.category_id == uom_storage_category:
                        qty = line.quantity
                        if line.uom_id.uom_type != 'reference':
                            qty = line.uom_id.with_context({'raise-exception': False})._compute_quantity(line.quantity, mb_uom or line.product_uom)
                        sum_total += qty
            client.topup_storage = sum_total

    @api.multi
    def _compute_contract_state(self):
        for client in self:
            state = "paid"
            today = datetime.today()
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
