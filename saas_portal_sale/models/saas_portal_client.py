from odoo import models, fields, api


class SaasPortalClient(models.Model):
    _inherit = 'saas_portal.client'

    contract_id = fields.Many2one(
        'account.analytic.account',
        string='Contract',
        readonly=True,
    )
    topup_users = fields.Integer('Additional users', compute='_get_user_topup_sum', help='from Topups', readonly=True)
    topup_storage_limit = fields.Integer('Additional storage (MB)',  compute='_get_storage_topup_sum', help='from Topups', readonly=True)
    topup_ids = fields.One2many('saas_portal.client_topup', inverse_name='client_id', string='Top ups')

    # Get the sum of Topuped Nr. of users
    @api.multi
    @api.depends('topup_ids.name', 'topup_ids.topup_users')
    def _get_user_topup_sum(self):
        for users in self:
            sum_total = 0.0

            for line in users.topup_ids:
                sum_total += line.topup_users
                users.update({
                    'topup_ids': sum_total
                })

    # Get the sum of Topuped Nr. of storage
    @api.multi
    @api.depends('topup_ids.name', 'topup_ids.topup_storage')
    def _get_storage_topup_sum(self):
        for storage in self:
            sum_total = 0.0

            for line in storage.topup_ids:
                sum_total += line.topup_storage
                storage.update({
                    'topup_ids': sum_total
                })


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