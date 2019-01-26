from odoo import models, fields, api, SUPERUSER_ID
import odoo
from odoo.tools.translate import _
from odoo.exceptions import ValidationError


class SaasPortalChangePlanWizard(models.TransientModel):
    _name = 'saas_portal.change_plan_of_client.wizard'
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
    def registry(self, dbname, **kwargs):
        self.ensure_one()
        m = odoo.modules.registry.Registry
        return m.new(dbname, **kwargs)

    @api.multi
    def change_saas_plan(self):
        self.cur_client_id.sync_client()

        if not self.new_plan_id:
            raise ValidationError(_("Please choose a new plan!"))

        new_max_users = int(self.new_plan_id.max_users) + int(self.cur_client_id.topup_users)
        new_total_storage_limit = self.new_plan_id.total_storage_limit + self.cur_client_id.topup_storage

        payload = [{'key': 'saas_client.max_users',
                        'value': new_max_users, 'hidden': True},
                       #{'key': 'saas_client.expiration_datetime',
                       # 'value': self.cur_client_id.expiration_datetime,
                       # 'hidden': True},
                       {'key': 'saas_client.total_storage_limit',
                        'value': new_total_storage_limit,
                        'hidden': True}]

        self.cur_client_id.upgrade(payload={'params': payload})

        # if servers differ
        if self.cur_client_id.server_id != self.new_plan_id.server_id:
            db_name = self.cur_client_id.name
            base_domain = self.env['ir.config_parameter'].sudo().get_param('saas_portal.base_saas_domain')
            if (self.old_plan_id.domain or base_domain) != (self.new_plan_id.domain or base_domain):
                # rename the DB if a server's domain is another one
                if (self.old_plan_id.domain or base_domain) in self.cur_client_id.name:
                    db_name = self.cur_client_id.name.replace((self.old_plan_id.domain or base_domain), (self.new_plan_id.domain or base_domain))
                    self.cur_client_id.rename_database(new_dbname=db_name)
            # TODO detach oauth application from the old server and create it on the new one
            old_server_db_name = self.cur_client_id.server_id.name
            with self.registry(old_server_db_name).cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, self._context)
                client_obj = env['saas_server.client'].sudo()
                app = client_obj.search([('client_id', '=', self.cur_client_id.client_id)], limit=1)
                if app:
                    app.unlink()
            new_server_db_name = self.new_plan_id.server_id.name
            with self.registry(new_server_db_name).cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, self._context)
                client_obj = env['saas_server.client'].sudo()
                app = client_obj.search([('client_id', '=', self.cur_client_id.client_id)], limit=1)
                if not app:
                    client_obj.create({
                        'name': db_name,
                        'client_id': self.cur_client_id.client_id,
                        'expiration_datetime': self.cur_client_id.expiration_datetime,
                        'trial': self.cur_client_id.trial,
                        'host': self.cur_client_id.host,
                    })
            self.cur_client_id.server_id = self.new_plan_id.server_id and self.new_plan_id.server_id.id or False

        self.cur_client_id.plan_id = self.new_plan_id.id
        self.cur_client_id.sync_client()

        action = {'type': 'ir.actions.act_window_close'}
        return action
