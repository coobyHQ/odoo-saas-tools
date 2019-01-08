from odoo import models, fields, api


class SaasPortalPlan(models.Model):
    _inherit = 'saas_portal.plan'

    free_subdomains = fields.Boolean(
        help='allow to choose subdomains for trials otherwise allow only after payment',
        default=True)
    non_trial_instances = fields.Selection(
        [('from_trial', 'From trial'), ('create_new', 'Create new')],
        string='Non-trial instances',
        help='Whether to use trial database or create new one when user make payment',
        required=True, default='create_new')
    topup_ids = fields.One2many('saas_portal.plan_topup', inverse_name='plan_id', string='Top ups')
    product_tmpl_id = fields.Many2one('product.template', 'Product')
    attribute_line_ids = fields.One2many(related='product_tmpl_id.attribute_line_ids',
                                         String='Product variants')

    product_variant_ids = fields.One2many('product.product',
                                          'saas_plan_id',
                                          'Product variants')
    contract_template_id = fields.Many2one('account.analytic.contract', string='Contract Template')

    @api.multi
    def _new_database_vals(self, vals):
        vals = super(SaasPortalPlan, self)._new_database_vals(vals)

        contract = self.env['account.analytic.account'].sudo().create({
            'name': vals['name'],
            'partner_id': vals['partner_id'],
            'recurring_invoices': True,
            'contract_template_id': self.contract_template_id and self.contract_template_id.id or False
        })
        if self.contract_template_id:
            contract._onchange_contract_template_id()

        vals['contract_id'] = contract.id
        return vals

    @api.multi
    def create_new_database(self, **kwargs):
        order_id = kwargs.get('order_id')
        if order_id: kwargs.pop('order_id', None)

        res = super(SaasPortalPlan, self).create_new_database(**kwargs)

        client_obj = self.env['saas_portal.client'].browse(res.get('id'))
        max_users = int(self.max_users)
        total_storage_limit = int(self.total_storage_limit)

        if order_id and client_obj and self.topup_ids:
            order = self.env['sale.order'].sudo().browse(int(order_id))
            params_list = []
            users = max_users
            storage = total_storage_limit
            for topup in self.topup_ids:
                order_lines = order.order_line.filtered(lambda line: line.product_id.id == topup.product_tmpl_id.id)
                if order_lines:
                    for line in order_lines:
                        if topup.topup_users:
                            users += int(topup.topup_users * line.product_uom_qty)
                        if topup.topup_storage:
                            storage += int(topup.topup_storage * line.product_uom_qty)
            if users != max_users:
                params_list.append({'key': 'saas_client.max_users', 'value': users})
            if storage != total_storage_limit:
                params_list.append({'key': 'saas_client.total_storage_limit', 'value': storage})

            if params_list:
                client_obj.upgrade(payload={'params': params_list})

        return res


