from odoo import models, fields, api


class SaasPortalClient(models.Model):
    _inherit = 'saas_portal.client'

    contract_id = fields.Many2one('account.analytic.account', string='Contract', readonly=True)
    contract_line_ids = fields.One2many(related='contract_id.recurring_invoice_line_ids',
                                        string='Product invoice lines', readonly=True)
    topup_users = fields.Integer('Additional users', compute='_get_user_topup_sum', help='from Topups', readonly=True)
    topup_storage = fields.Integer('Additional storage (MB)',  compute='_get_storage_topup_sum',
                                         help='from Topups', readonly=True)
    topup_ids = fields.One2many('saas_portal.client_topup', inverse_name='client_id', string='Top ups')
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
    def act_show_contract(self):
        # Todo This example opens contract view
        #    @return: the contract view

        self.ensure_one()
        contract_type = self._context.get('contract_type')

        res = self._get_act_window_contract_xml(contract_type)
        res.update(
            context=dict(
                self.env.context,
                search_default_recurring_invoices=True,
                search_default_not_finished=True,
                search_default_partner_id=self.id,
                default_partner_id=self.id,
                default_recurring_invoices=True,
                default_pricelist_id=self.property_product_pricelist.id,
            ),
        )
        return res


class SaasPortalClientTopup (models.Model):
    _name = 'saas_portal.client_topup'
    _description = 'SaaS Client Topups (addons)'
    _inherit = ['sale.order.line']

  #  name = fields.Char('Topup name', required=True)
  #  summary = fields.Char(related='plan_id.summary', string='Summary')
    client_id = fields.Many2one('saas_portal.client', 'Client Topup', required=True)

  #  product_tmpl_id = fields.Many2one('product.template', 'Product Template', domain=[('saas_product_type', '=', 'addon')], required=True)
    plan_id = fields.Many2one(related='client_id.plan_id', string='Plan', required=True)
    topup_users = fields.Integer(string='# of Extra Users', default=0)
    topup_storage = fields.Integer(string='# of Extra Storage (MB)', default=0)




""""
    qty_delivered > sale.order.line
    topup_users = fields.Integer(related='plan_id.topup_users', string='# of Extra Users', default=0)
    topup_storage = fields.Integer(related='plan_id.topup_storage', string='# of Extra Storage (MB)', default=0)


    product_tmpl_id = fields.Many2one('product.template', 'Product Template', domain=[('saas_product_type', '=', 'addon')], required=True)
    plan_id = fields.Many2one('saas_portal.plan', string='Plan', required=True)
    topup_users = fields.Integer('# of Extra Users', default=1)
    topup_storage = fields.Integer('# of Extra Storage (MB)', default=0)
"""