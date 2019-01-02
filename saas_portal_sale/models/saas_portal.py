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
    product_variant_ids = fields.One2many('product.product',
                                          'saas_plan_id',
                                          'Product variants')

    @api.multi
    def _new_database_vals(self, vals):
        vals = super(SaasPortalPlan, self)._new_database_vals(vals)

        contract = self.env['account.analytic.account'].sudo().create({
            'name': vals['name'],
            'partner_id': vals['partner_id'],
            'recurring_invoices': True,
        })

        vals['contract_id'] = contract.id
        return vals

    @api.multi
    def create_new_database(self, **kwargs):
        res = super(SaasPortalPlan, self).create_new_database(**kwargs)

        params_list = []
        client_obj = self.env['saas_portal.client'].browse(res.get('id'))
        # ir_params = self.env['ir.config_parameter'].sudo()
        max_users = self.max_users # or ir_params.sudo().get_param('saas_client.max_users')
        total_storage_limit = self.total_storage_limit # or ir_params.sudo().get_param('saas_client.total_storage_limit')

        if client_obj and self.topup_ids:
            users = int(max_users)
            storage = int(total_storage_limit)
            for topup in self.topup_ids:
                if topup.topup_users: users += topup.topup_users
                if topup.topup_storage: storage += topup.topup_storage
            if users:
                params_list.append({'key': 'saas_client.max_users', 'value': users})
            if storage:
                params_list.append({'key': 'saas_client.total_storage_limit', 'value': storage})

            if params_list:
                client_obj.upgrade(payload={'params': params_list})

        return res


class SaasPortalClient(models.Model):
    _inherit = 'saas_portal.client'

    contract_id = fields.Many2one(
        'account.analytic.account',
        string='Contract',
        readonly=True,
    )
