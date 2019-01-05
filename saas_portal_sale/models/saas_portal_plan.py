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


