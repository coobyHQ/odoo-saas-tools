from odoo import models, fields, api


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

    # Todo Get the the state of billing of contract
    @api.multi
    @api.depends('contract_id')
    def _compute_contract_state(self):
        for contract in self:
            state_paid = "paid"
            state_open = "amount"
            state = ""

            for line in contract.contract_id:
                ({state == state_paid
                })

    # Todo example from contract module
    """
    def _compute_contract_count(self):
        contract_model = self.env['account.analytic.account']
        today = fields.Date.today()
        fetch_data = contract_model.read_group([
            ('recurring_invoices', '=', True),
            ('partner_id', 'child_of', self.ids),
            '|',
            ('date_end', '=', False),
            ('date_end', '>=', today)],
            ['partner_id', 'contract_type'], ['partner_id', 'contract_type'],
            lazy=False)
        result = [[data['partner_id'][0], data['contract_type'],
                   data['__count']] for data in fetch_data]
        for partner in self:
            partner_child_ids = partner.child_ids.ids + partner.ids
            partner.sale_contract_count = sum([
                r[2] for r in result
                if r[0] in partner_child_ids and r[1] == 'sale'])
            partner.purchase_contract_count = sum([
                r[2] for r in result
                if r[0] in partner_child_ids and r[1] == 'purchase'])
    """
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
