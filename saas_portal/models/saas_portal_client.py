import simplejson
import requests
from datetime import datetime, timedelta
from odoo import api, exceptions, fields, models
from odoo.tools.translate import _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from werkzeug.exceptions import Forbidden

import logging
_logger = logging.getLogger(__name__)


class SaasPortalClient(models.Model):
    _name = 'saas_portal.client'
    _description = 'Client Instances'
    _mail_flat_thread = False

    _inherit = ['mail.thread', 'mail.activity.mixin', 'saas_portal.database', 'saas_base.client']

    def _get_default_subdomain(self):
        return self.plan_id.dbname_template

    name_txt = fields.Char('to delete', store=True)
    summary = fields.Char('Summary', compute='_get_compose_summary', store=True)
    partner_id = fields.Many2one('res.partner', string='Partner', track_visibility='onchange', readonly=True)
    plan_id = fields.Many2one('saas_portal.plan', string='Plan',
                              track_visibility='onchange', ondelete='set null', readonly=True)
    subdomain = fields.Char('Sub Domain', default=_get_default_subdomain)
    plan_image = fields.Binary(related='plan_id.logo', string="Plan logo", readonly=True)
    plan_max_users = fields.Integer(related='plan_id.max_users', string="Plan max allowed users", readonly=True)
    plan_max_storage = fields.Integer(related='plan_id.max_storage', string="Plan max allowed Storage", readonly=True)
    topup_storage = fields.Integer('Additional storage (MB)', help='from Topups', default=0, readonly=True)
    total_storage_limit = fields.Integer('Total storage limit (MB)', store=True, compute='_compute_total_storage_limit',
                                         inverse='_write_total_storage_limit', help='Overall storage limit')
    plan_lang = fields.Selection(related='plan_id.lang', readonly=True)
    plan_branch_id = fields.Many2one(related='plan_id.branch_id', string="Plan Branch", store=True, readonly=True)
    user_id = fields.Many2one(
        'res.users', default=lambda self: self.env.user, string='Salesperson')
    notification_sent = fields.Boolean(string='Notification on upcoming expiration sent', default=False, readonly=True,
                                       help='Notification on the upcoming expiration has been sent')
    notification_storage = fields.Boolean(string='Notification on storage limit sent', default=False, readonly=True,
                                             help='Notification on reaching the storage limit has been sent')
    active = fields.Boolean(default=True, compute='_compute_active', store=True)
    block_on_expiration = fields.Boolean(related='plan_id.block_on_expiration', readonly=True)
    block_on_storage_exceed = fields.Boolean(related='plan_id.block_on_storage_exceed', readonly=True)
    storage_exceed = fields.Boolean('Storage limit exceeded', default=False)
    # Todo, field not used?? Better taking from plan. LUH
    trial_hours = fields.Integer(related='plan_id.expiration', string='Initial period for trial (hours)',
                                 help='Initial period in hours for trials',
                                 readonly=True)
    note = fields.Html('Note')
    login_allowed = fields.Boolean('Login Request Allowed', default=False)
    login_permission_token = fields.Char('Login Permission Token')
    login_permission_url = fields.Char('Login Permission URL', compute='_get_login_permission_url')

    # TODO: use new api for tracking
    _track = {
        'expired': {
            'saas_portal.mt_expired':
            lambda self, cr, uid, obj, ctx=None: obj.expired
        }
    }

    @api.multi
    @api.depends('plan_id', 'plan_id.max_storage', 'topup_storage')
    def _compute_total_storage_limit(self):
        for client in self:
            client.total_storage_limit = client.plan_max_storage + client.topup_storage
            client.upgrade(payload={'params': [
                {'key': 'saas_client.total_storage_limit', 'value': client.total_storage_limit, 'hidden': True}]})

    def _write_total_storage_limit(self):
        for client in self:
            client.upgrade(payload={'params': [
                {'key': 'saas_client.total_storage_limit', 'value': client.total_storage_limit, 'hidden': True}]})

    @api.multi
    def _get_compose_summary(self):
        for record in self:
            plan = record.plan_id and record.plan_id.name or ''
            subdomain = record.subdomain or ''
            client = record.partner_id and record.partner_id.name or ''
            new_name = "%s, %s, %s" % (plan, subdomain, client)
            record.summary = new_name

    @api.multi
    @api.depends('state')
    def _compute_active(self):
        for record in self:
            record.active = record.state != 'deleted'

    @api.multi
    @api.depends('login_permission_token')
    def _get_login_permission_url(self):
        config_obj = self.env['ir.config_parameter']
        url = config_obj.sudo().get_param('web.base.url') + '/saas_portal/login_permission/'
        for record in self:
            if record.login_permission_token:
                record.login_permission_url = url + record.login_permission_token

    @api.model
    def _cron_suspend_expired_clients(self):
        payload = {
            'params': [{'key': 'saas_client.suspended', 'value': '1', 'hidden': True}],
        }
        now = fields.Datetime.now()
        expired = self.search([
            ('expiration_datetime', '<', now),
            ('expired', '=', False)
        ])
        expired.write({'expired': True})
        for record in expired:
            if record.trial or record.block_on_expiration:
                template = self.env.ref(
                    'saas_portal.email_template_has_expired_notify')
                record.message_post_with_template(
                    template.id, composition_mode='comment')

                record.upgrade(payload)
                # if upgraded without exceptions then change the state
                record.state = 'pending'

    @api.model
    def _cron_notify_expired_clients(self):
        # send notification about expiration by email
        notification_delta = int(self.env['ir.config_parameter'].sudo(
        ).get_param('saas_portal.expiration_notify_in_advance', '0'))
        if notification_delta > 0:
            records = self.search([('expiration_datetime', '<=', (datetime.now() + timedelta(days=notification_delta)).strftime(DEFAULT_SERVER_DATETIME_FORMAT)),
                                   ('notification_sent', '=', False)])
            records.write({'notification_sent': True})
            for record in records:
                template = self.env.ref(
                    'saas_portal.email_template_expiration_notify')
                record.with_context(days=notification_delta).message_post_with_template(
                    template.id, composition_mode='comment')

    def unlink(self):
        for obj in self:
            to_search1 = [('application_id', '=', obj.id)]
            tokens = self.env['oauth.access_token'].search(to_search1)
            tokens.unlink()
            # TODO: it seems we don't need stuff below
            # to_search2 = [('database', '=', obj.name)]
            # user_ids = user_model.search(to_search2)
            # if user_ids:
            #    user_model.unlink(user_ids)
            # odoo.service.db.exp_drop(obj.name)
        return super(SaasPortalClient, self).unlink()

    @api.multi
    def write(self, values):
        if 'expiration_datetime' in values:
            payload = {
                'params': [{'key': 'saas_client.expiration_datetime', 'value': values['expiration_datetime'], 'hidden': True}],
            }

            for record in self:
                record.upgrade(payload)

        result = super(SaasPortalClient, self).write(values)

        return result

    @api.multi
    def rename_subdomain(self, new_subdomain):
        self.ensure_one()
        new_name = "%s.%s" % (new_subdomain, self.domain)
        self.rename_database(new_dbname=new_name, new_subdomain=new_subdomain)

    @api.multi
    def rename_database(self, new_dbname, new_subdomain):
        self.ensure_one()

        saas_portal_database = self.env['saas_portal.database'].sudo()
        if saas_portal_database.search([('name', '=', new_dbname)]):
            raise ValidationError(
                _("This database name already exists: "
                  "'%s'") % new_dbname
            )

        # TODO async
        state = {
            'd': self.name,
            'client_id': self.client_id,
            'new_dbname': new_dbname,
        }
        req, req_kwargs = self.server_id._request_server(
            path='/saas_server/rename_database', state=state, client_id=self.client_id)
        res = requests.Session().send(req, **req_kwargs)
        _logger.info('delete database: %s', res.text)
        if res.status_code != 500:
            self.name = new_dbname
            self.subdomain = new_subdomain

    @api.multi
    def sync_client(self):
        self.ensure_one()
        self.server_id.action_sync_server(updating_client_ID=self.client_id)

    @api.multi
    def check_partner_access(self, partner_id):
        for record in self:
            if record.partner_id.id != partner_id:
                raise Forbidden

    @api.multi
    def duplicate_database(self, dbname=None, partner_id=None, expiration=None):
        self.ensure_one()
        p_client = self.env['saas_portal.client']
        p_server = self.env['saas_portal.server']

        owner_user = self.env['res.users'].search(
            [('partner_id', '=', partner_id)], limit=1) or self.env.user

        server = self.server_id
        if not server:
            server = p_server.get_saas_server()

        server.action_sync_server()

        vals = {'name': dbname,
                'server_id': server.id,
                'plan_id': self.plan_id.id,
                'partner_id': partner_id or self.partner_id.id,
                }
        if expiration:
            now = datetime.now()
            delta = timedelta(hours=expiration)
            vals['expiration_datetime'] = (
                now + delta).strftime(DEFAULT_SERVER_DATETIME_FORMAT)

        client = p_client.create(vals)
        client_id = client.client_id

        owner_user_data = {
            'user_id': owner_user.id,
            'login': owner_user.login,
            'name': owner_user.name,
            'email': owner_user.email,
            'password': None,
        }

        state = {
            'd': client.name,
            'e': client.expiration_datetime,
            'r': client.public_url + 'web',
            'owner_user': owner_user_data,
            'public_url': client.public_url,
            'db_template': self.name,
            'disable_mail_server': True,
        }

        scope = ['userinfo', 'force_login', 'trial', 'skiptheuse']

        req, req_kwargs = server._request_server(path='/saas_server/new_database',
                                                 state=state,
                                                 client_id=client_id,
                                                 scope=scope,)
        res = requests.Session().send(req, **req_kwargs)

        if not res.ok:
            raise Warning(_('Reason: %s \n Message: %s') %
                          (res.reason, res.content))
        try:
            data = simplejson.loads(res.text)
        except Exception as e:
            _logger.error('Error on parsing response: %s\n%s' %
                          ([req.url, req.headers, req.body], res.text))
            raise

        data.update({'id': client.id})

        return data

    @api.multi
    def get_upgrade_database_payload(self):
        self.ensure_one()
        return {'params': [{'key': 'saas_client.expiration_datetime',
                            'value': self.expiration_datetime,
                            'hidden': True}]}

    @api.multi
    def send_params_to_client_db(self):
        for record in self:
            payload = {
                'params': [{'key': 'saas_client.max_users',
                            'value': record.max_users, 'hidden': True},
                           {'key': 'saas_client.expiration_datetime',
                            'value': record.expiration_datetime,
                            'hidden': True},
                           {'key': 'saas_client.total_storage_limit',
                            'value': record.total_storage_limit,
                            'hidden': True}],
            }
            self.env['saas.config'].do_upgrade_database(payload, record)

    # send email about change of expiration date
    @api.multi
    def send_expiration_info_to_partner(self):
        for record in self:
            if record.expiration_datetime:
                template = self.env.ref(
                    'saas_portal.email_template_expiration_datetime_updated')
                record.message_post_with_template(
                    template.id, composition_mode='comment')

    # Subscription storage upcoming exceed
    @api.multi
    def storage_usage_near_limit(self):
        for r in self:
            if r.expired is True:
                return

            if (r.total_storage > r.total_storage_limit - 20) and r.notification_storage is False: # if the db grows to within 20MB of limit?
                r.write({'notification_storage': True})
                template = self.env.ref('saas_portal.email_template_upcoming_storage_exceed')
                r.message_post_with_template(
                    template.id, composition_mode='mass_mail')
            if (r.total_storage > r.total_storage_limit - 25) and r.notification_storage is True: # if it falls back to 25MB less?
                r.write({'notification_storage': False})

    # Subscription storage exceeded
    @api.multi
    def storage_usage_monitoring(self):
        payload = {
            'params': [{'key': 'saas_client.suspended',
                        'value': '1',
                        'hidden': True}],
        }
        for r in self:
            if r.expired is True:
                return

            if r.total_storage_limit < r.file_storage + r.db_storage and r.storage_exceed is False:
                r.write({'storage_exceed': True})
                template = self.env.ref(
                    'saas_portal.email_template_storage_exceed')
                r.message_post_with_template(
                    template.id, composition_mode='comment')

                if r.block_on_storage_exceed:
                    self.env['saas.config'].do_upgrade_database(payload, r)
            if not r.total_storage_limit >= r.file_storage + r.db_storage and r.storage_exceed is True:
                r.write({'storage_exceed': False})
