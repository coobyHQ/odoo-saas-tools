from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.exceptions import ValidationError


class SaasChangePlanWizard(models.TransientModel):
    _name = 'saas_portal_sale.change_plan_of_client.wizard'
    _description = 'SaaS Portal Client Plan Change'

    @api.model
    def _get_client_id(self):
        return self._context.get('active_id', False)

    cur_client_id = fields.Many2one(comodel_name="saas_portal.client", string="Client",
                                   required=True, ondelete="cascade", default=_get_client_id, auto_join=True)

    old_plan_id = fields.Many2one(string="Current Plan", readonly=True, comodel_name='saas_portal.plan',
                                  related='cur_client_id.plan_id')
    new_plan_id = fields.Many2one(string="New plan", comodel_name='saas_portal.plan')

    saas_plan_change_type = fields.Selection([
        ('upgrade', 'Upgrade the plan'),
        ('downgrade', 'Downgrade the plan ')],
        string='SaaS Plan Change Type')
    plan_id_desc = fields.Html(string="Plan Description", readonly=True, related='new_plan_id.website_description')
    message = fields.Text(string="Plan Change Comment", help="Comment at change of plan from Staff",
                          required=True)

    @api.onchange('saas_plan_change_type')
    def onchange_saas_plan_change_type(self):
        domain = {}
        if self.saas_plan_change_type and self.old_plan_id:
            if self.saas_plan_change_type == 'upgrade':
                domain['new_plan_id'] = [('id', 'in', self.old_plan_id.upgrade_path_ids.ids)]
            else:
                domain['new_plan_id'] = [('id', 'in', self.old_plan_id.downgrade_path_ids.ids)]
        else:
            domain['new_plan_id'] = [('id', '=', 0)]
        if domain and self.new_plan_id:
            possible_plans = self.env['saas_portal.plan'].search(domain['new_plan_id'])
            if not possible_plans or self.new_plan_id.id not in possible_plans.ids:
                self.new_plan_id = False
        return {'domain': domain}

    @api.multi
    def change_saas_plan(self):
        # TODO
        action = self.env.ref('saas_portal.action_templates').read()[0]
        if action:
            action['views'] = [(self.env.ref('saas_portal.view_databases_form').id, 'form')]
            action['res_id'] = self.new_plan_id.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action
