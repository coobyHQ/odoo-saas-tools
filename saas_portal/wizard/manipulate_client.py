from odoo import models, fields, api, SUPERUSER_ID
import odoo
from odoo.tools.translate import _
from odoo.exceptions import ValidationError


class SaasPortalManipulateClientWizard(models.TransientModel):
    _name = 'saas_portal.manipulate_client.wizard'
    _description = 'SaaS Portal Client Manipulation'
    """
    @api.model
    def default_get(self, fields):
        res = super(SaasPortalManipulateClientWizard, self).default_get(fields)
        res['active_model'] = self._context.get('active_model')

    """
    @api.model
    def _get_client_id(self):
        return self._context.get('active_id', False)

    action = fields.Selection([
        ('rename', 'Rename Database'),
        ('server_change', 'Change the Server (move)'),
        ('plan_change', 'Change the plan'),
        ('delete', 'Delete the Database')],
        string='Type of Manipulation', default='server_change')
    active_id2 = fields.Char()
    active_model = fields.Char()
    client_email = fields.Char(default=True, readonly=True)  # Todo get valid email
    cur_client_id = fields.Many2one(comodel_name="saas_portal.client", string="Client Database name",
                                    required=True, ondelete="cascade", default=_get_client_id, auto_join=True)

    # Change of the plan
    saas_plan_change_type = fields.Selection([
        ('upgrade', 'Upgrade the plan'),
        ('downgrade', 'Downgrade the plan ')],
        string='SaaS Plan Change Type', default='upgrade')
    old_plan_id = fields.Many2one(string="Current Plan", readonly=True, comodel_name='saas_portal.plan',
                                  related='cur_client_id.plan_id')
    new_plan_id = fields.Many2one(string="New plan", comodel_name='saas_portal.plan')
    plan_id_desc = fields.Html(string="Plan Description", readonly=True, related='new_plan_id.website_description')

    # Change of the server
    current_server_id = fields.Many2one(string="Current Server", readonly=True, comodel_name='saas_portal.server',
                                  related='cur_client_id.server_id')
    new_server_id = fields.Many2one('saas_portal.server', string='Server')

    # Rename Subdomain name
    domain = fields.Char(related='cur_client_id.domain', string='Domain', readonly=True)
    subdomain = fields.Char('New Subdomain', required=False)

    mail_template = fields.Many2one('mail.template', string="Client Change Comment",
                                    help="Mail template text for change of client")  # Todo domain=
    message = fields.Text(string="Client Change Comment", help="Individual comment at change of client from Staff")

    # Change of the plan
    @api.onchange('client_manipulation_type')
    def onchange_client_manipulation_type(self):
        domain = {}
        if self.client_manipulation_type and self.old_plan_id:
            if self.client_manipulation_type == 'upgrade':
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
        new_total_storage_limit = self.new_plan_id.max_storage + self.cur_client_id.topup_storage

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
                        'host': self.cur_client_id.name,
                        'state': 'open'
                    })
            self.cur_client_id.server_id = self.new_plan_id.server_id and self.new_plan_id.server_id.id or False

        self.cur_client_id.plan_id = self.new_plan_id.id
        self.cur_client_id.sync_client()

        return self.send_email

    # Change of the server
    @api.multi
    def change_saas_server(self):
        self.cur_client_id.sync_client()

        if not self.new_server_id:
            raise ValidationError(_("Please choose a new server!"))

        db_name = self.cur_client_id.name
        base_domain = self.env['ir.config_parameter'].sudo().get_param('saas_portal.base_saas_domain')
        if (self.cur_client_id.server_id.domain or base_domain) != (self.new_server_id.domain or base_domain):
            # rename the DB if a server's domain is another one
            if (self.cur_client_id.server_id.domain or base_domain) in self.cur_client_id.name:
                db_name = self.cur_client_id.name.replace((self.cur_client_id.server_id.domain or base_domain),
                                                          (self.new_server_id.domain or base_domain))
                self.cur_client_id.rename_database(new_dbname=db_name)
        old_server_db_name = self.cur_client_id.server_id.name
        with self.registry(old_server_db_name).cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, self._context)
            client_obj = env['saas_server.client'].sudo()
            app = client_obj.search([('client_id', '=', self.cur_client_id.client_id)], limit=1)
            if app:
                app.unlink()
        new_server_db_name = self.new_server_id.name
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
                    'host': self.cur_client_id.name,
                    'state': 'open'
                })
        self.cur_client_id.server_id = self.new_server_id and self.new_server_id.id or False
        self.cur_client_id.sync_client()

        return self.send_email

    # Rename Subdomain name
    @api.multi
    def rename_subdomain(self):
        self.ensure_one()
        self.cur_client_id.rename_subdomain(new_subdomain=self.subdomain)
        return self.send_email

    # Send Email and Exit
    @api.multi
    def send_email(self):
        if not self.client_email:
            raise ValidationError(_("A client does not have an e-mail address, please add it!"))
        instance = self.env[self.active_model].browse(int(self.active_id2))
        email_template_instance_has_changed = self.env.ref('saas_portal.email_template_instance_has_changed',
                                                           raise_if_not_found=False)
        if email_template_instance_has_changed:
            email_template_instance_has_changed.send_mail(instance.id, force_send=True)
        else:
            raise ValidationError(("No email template found for requesting login permission from the client!"))

        action = {'type': 'ir.actions.act_window_close'}
        return action
