from odoo import models, fields, api


class SaasChangePlanWizard(models.TransientModel):
    _name = 'saas_portal_sale.change_plan_of_client.wizard'
    _description = 'SaaS Portal Client Plan Change'

    @api.model
    def _get_client_id(self):
        return self._context.get('active_id', False)

    cur_client_id = fields.Many2one(comodel_name="saas_portal.client", string="Client",
                                   required=True, ondelete="cascade", default=_get_client_id, auto_join=True)

    old_plan_id = fields.Many2one(string="Current Plan", readonly=True, comodel_name='saas_portal.client.plan_id',
                                  related='cur_client_id.plan_id')
    new_plan_id = fields.Many2one(string="New plan", comodel_name='saas_portal.plan')

    saas_plan_change_type = fields.Selection([
        ('upgrade', 'Upgrade the plan'),
        ('downgrade', 'Downgrade the plan ')],
        string='SaaS Plan Change Type')
    """
    plan_id_desc = fields.Text(string="Plan Description", readonly="1",
                                related='plan_id.description')
    """
    message = fields.Text(string="Plan Change Comment", help="Comment at change of plan from Staff",
                          required="1")
