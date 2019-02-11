from odoo import models, fields, api


class SaasPortalPlan(models.Model):
    _inherit = 'saas_portal.plan'

    @api.depends('product_tmpl_id', 'product_tmpl_id.accessory_product_ids')
    def _compute_product_tmpl_topup_ids(self):
        for plan in self:
            product_ids = []
            if plan.product_tmpl_id and plan.product_tmpl_id.accessory_product_ids:
                for pr in plan.product_tmpl_id.accessory_product_ids:
                    product_ids.append(pr.id)
            plan.product_tmpl_topup_ids = product_ids

    free_subdomains = fields.Boolean(
        help='allow to choose subdomains for trials otherwise allow only after payment',
        default=True)
    non_trial_instances = fields.Selection(
        [('from_trial', 'From trial'), ('create_new', 'Create new')],
        string='Non-trial instances',
        help='Whether to use trial database or create new one when user make payment',
        required=True, default='create_new')
    product_tmpl_id = fields.Many2one('product.template', 'Product')
    product_tmpl_topup_ids = fields.One2many(
        string='Topup Products', store=False,
        comodel_name='product.product',
        compute='_compute_product_tmpl_topup_ids'
    )
    attribute_line_ids = fields.One2many(related='product_tmpl_id.attribute_line_ids',
                                         String='Product variants')
    contract_template_id = fields.Many2one('account.analytic.contract', string='Contract Template')

    @api.multi
    def _new_database_vals(self, vals):
        vals = super(SaasPortalPlan, self)._new_database_vals(vals)

        if not vals.get('trial', False):
            contract = self.env['account.analytic.account'].sudo().create({
                'name': vals['subdomain'],
                'partner_id': vals['partner_id'],
                'recurring_invoices': True,
                'contract_template_id': self.contract_template_id and self.contract_template_id.id or False
            })
            if self.contract_template_id:
                contract._onchange_contract_template_id()
            vals['contract_id'] = contract.id
        return vals

    def get_topup_info(self, order, client):
        additional_invoice_lines = []
        users = int(self.max_users)
        storage = int(self.max_storage)
        if client:
            users += int(client.topup_users)
            storage += int(client.topup_storage)
        mb_uom = self.env.ref('saas_portal_sale.product_uom_megabyte', raise_if_not_found=False)
        users_uom = self.env.ref('saas_portal_sale.product_uom_users', raise_if_not_found=False)
        topup_order_lines = order.order_line.filtered(lambda line: line.product_id.is_saas and line.product_id.saas_product_type == 'topup')
        for topup_line in topup_order_lines:
            topup = topup_line.product_id
            if topup.id in self.product_tmpl_topup_ids.ids:
                if topup.saas_topup_type == 'users':
                    qty = topup_line.product_uom_qty
                    if topup_line.product_uom.uom_type != 'reference':
                        qty = topup_line.product_uom.with_context({'raise-exception':False})._compute_quantity(topup_line.product_uom_qty, users_uom or topup_line.product_uom)
                    users += int(qty)
                if topup.saas_topup_type == 'storage':
                    qty = topup_line.product_uom_qty
                    if topup_line.product_uom.uom_type != 'reference':
                        qty = topup_line.product_uom._compute_quantity(topup_line.product_uom_qty, mb_uom or topup_line.product_uom)
                    storage += int(qty)
                if topup.saas_topup_contract_template_id and client and client.contract_id:
                    for inv_line in topup.saas_topup_contract_template_id.recurring_invoice_line_ids:
                        additional_invoice_lines.append({
                            'analytic_account_id': client.contract_id and client.contract_id.id or False,
                            'product_id': inv_line.product_id.id,
                            'name': inv_line.name,
                            'quantity': inv_line.quantity * topup_line.product_uom_qty,
                            'uom_id': inv_line.uom_id.id,
                            'automatic_price': inv_line.automatic_price,
                            'price_unit': inv_line.price_unit,
                        })
        return users, storage, additional_invoice_lines

    @api.multi
    def create_new_database(self, **kwargs):
        order_id = kwargs.get('order_id')
        if order_id: kwargs.pop('order_id', None)

        res = super(SaasPortalPlan, self).create_new_database(**kwargs)

        client_obj = self.env['saas_portal.client'].browse(res.get('id'))
        max_users = int(self.max_users)
        max_storage = int(self.max_storage)

        if order_id and client_obj and self.product_tmpl_topup_ids:
            order = self.env['sale.order'].sudo().browse(int(order_id))
            users, storage, additional_invoice_lines = self.get_topup_info(order, client_obj)
            params_list = []
            client_vals = {}
            if users != max_users:
                params_list.append({'key': 'saas_client.max_users', 'value': users})
                client_vals.update(max_users=str(users))
            if storage != max_storage:
                params_list.append({'key': 'saas_client.total_storage_limit', 'value': storage})
                client_vals.update(total_storage_limit=storage)
            if params_list:
                client_obj.upgrade(payload={'params': params_list})
                if client_vals: client_obj.write(client_vals)
            if client_obj.contract_id and additional_invoice_lines:
                for invoice_line in additional_invoice_lines:
                    self.env['account.analytic.invoice.line'].sudo().create(invoice_line)

        return res


