from odoo import models, fields, api

class SaasPortalPlan(models.Model):
    _inherit = 'saas_portal.plan'

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