import requests
import random
import string
from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class SaasPortalCreateClient(models.TransientModel):
    _name = 'saas_portal.create_client'

    def _default_plan_id(self):
        return self._context.get('active_id')

    def _default_name(self):
        plan_id = self._default_plan_id()
        if plan_id:
            plan = self.env['saas_portal.plan'].browse(plan_id)
            return plan.generate_dbname(raise_error=False)
        return ''

    name = fields.Char('Database name', required=True, default=_default_name)
    plan_id = fields.Many2one(
        'saas_portal.plan', string='Plan',
        readonly=True, default=_default_plan_id)
    partner_id = fields.Many2one('res.partner', string='Partner')
    user_id = fields.Many2one('res.users', string='User')
    notify_user = fields.Boolean(
        help='Notify user by email when database will have been created',
        default=True)
    async_creation = fields.Boolean(
        'Asynchronous',
        default=False, help='Asynchronous creation of client base')
    trial = fields.Boolean('Trial')

    @api.onchange('user_id')
    def update_partner(self):
        if self.user_id:
            self.partner_id = self.user_id.partner_id

    @api.multi
    def apply(self):
        self.ensure_one()
        plan_id = self.plan_id
        res = plan_id.create_new_database(
            dbname=self.name,
            partner_id=self.partner_id.id,
            user_id=self.user_id.id,
            notify_user=self.notify_user,
  # moved   support_team_id=self.support_team_id.id,
            async=self.async_creation,
            trial=self.trial)
        if self.async_creation:
            return
        client = self.env['saas_portal.client'].browse(res.get('id'))
        client.server_id.action_sync_server()
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'saas_portal.client',
            'res_id': client.id,
            'target': 'current',
        }


class SaasPortalDuplicateClient(models.TransientModel):
    _name = 'saas_portal.duplicate_client'

    def _default_client_id(self):
        return self._context.get('active_id')

    def _default_partner(self):
        client_id = self._default_client_id()
        if client_id:
            client = self.env['saas_portal.client'].browse(client_id)
            return client.partner_id
        return ''

    def _default_expiration(self):
        client_id = self._default_client_id()
        if client_id:
            client = self.env['saas_portal.client'].browse(client_id)
            return client.plan_id.expiration
        return ''

    name = fields.Char('Database Name', required=True)
    client_id = fields.Many2one(
        'saas_portal.client', string='Base Client',
        readonly=True, default=_default_client_id)
    expiration = fields.Integer('Expiration', default=_default_expiration)
    partner_id = fields.Many2one(
        'res.partner', string='Partner', default=_default_partner)

    @api.multi
    def apply(self):
        self.ensure_one()
        res = self.client_id.duplicate_database(
            dbname=self.name, partner_id=self.partner_id.id, expiration=None)
        client = self.env['saas_portal.client'].browse(res.get('id'))
        client.server_id.action_sync_server()
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'saas_portal.client',
            'res_id': client.id,
            'target': 'current',
        }


class SaasPortalRenameDatabase(models.TransientModel):
    _name = 'saas_portal.rename_database'

    def _default_client_id(self):
        return self._context.get('active_id')
    # Todo domain field
    domain = fields.Char(related='client_id.domain', string='Domain', readonly=True)
    subdomain = fields.Char('New Subdomain', required=True)
    client_id = fields.Many2one('saas_portal.client', string='Base Client',
                                readonly=True, default=_default_client_id)

    @api.multi
    def apply(self):
        self.ensure_one()
        self.client_id.rename_subdomain(new_subdomain=self.subdomain)
        return {
            'type': 'ir.actions.act_window_close',
        }


class SaasPortalEditDatabase(models.TransientModel):
    _name = 'saas_portal.edit_database'

    name = fields.Char(readonly=True)
    active_id = fields.Char()
    active_model = fields.Char()
    edit_database_url = fields.Char(readonly=True)
    login_allowed = fields.Boolean('Login Request Allowed', default=False)
    client_email = fields.Char(readonly=True)

    @api.model
    def default_get(self, fields):
        res = super(SaasPortalEditDatabase, self).default_get(fields)
        res['active_model'] = self._context.get('active_model')
        res['active_id'] = self._context.get('active_id')

        login_allowed = False
        active_record = self.env[res['active_model']].browse(int(res['active_id']))
        if res['active_model'] == 'saas_portal.client':
            if active_record.login_allowed:
                login_allowed = True
            res['client_email'] = active_record and active_record.partner_id and active_record.partner_id.email
        elif res['active_model'] == 'saas_portal.database':
            login_allowed = True
        else:
            active_record = active_record.template_id
            login_allowed = True
        res['name'] = active_record.name
        res['edit_database_url'] = active_record._request_url('/saas_server/edit_database')
        res['login_allowed'] = login_allowed
        return res

    @api.multi
    def login_to_instance(self):
        if not self.edit_database_url:
            raise ValidationError(_("No URL to login to!"))

        if self.active_model == 'saas_portal.client':
            instance = self.env[self.active_model].browse(int(self.active_id))
            instance.login_allowed = False

        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'name': 'Login redirection',
            'url': self.edit_database_url
        }

    @api.multi
    def request_permission(self):
        if not self.client_email:
            raise ValidationError(_("A client does not have an e-mail address, please add it!"))

        instance = self.env[self.active_model].browse(int(self.active_id))
        instance.login_permission_token = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))

        template = None
        ir_config_param = self.env['ir.config_parameter'].sudo()
        login_permission_email_template = self.env.ref('saas_portal.login_permission_email_template', raise_if_not_found=False)
        if login_permission_email_template:
            login_permission_email_template.send_mail(instance.id, force_send=True)
        else:
            raise ValidationError(("No email template found for requesting login permission from the client!"))
