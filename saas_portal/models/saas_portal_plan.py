import simplejson
import werkzeug
import requests
from datetime import datetime, timedelta

from odoo import api, exceptions, fields, models
from odoo.tools import scan_languages
from odoo.tools.translate import _
from odoo.addons.base.res.res_partner import _tz_get
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

from odoo.addons.saas_base.exceptions import MaximumTrialDBException
from odoo.addons.saas_base.exceptions import MaximumDBException

import logging
_logger = logging.getLogger(__name__)


@api.multi
def _compute_host(self):
    base_saas_domain = self.env['ir.config_parameter'].sudo(
    ).get_param('saas_portal.base_saas_domain')
    for r in self:
        host = r.name
        if base_saas_domain and '.' not in r.name:
            host = '%s.%s' % (r.name, base_saas_domain)
        r.host = host


class SaasPortalPlan(models.Model):
    _name = 'saas_portal.plan'
    _description = 'SaaS Plan (templates)'
    name = fields.Char('Plan', required=True)
    summary = fields.Char('Summary')
    template_id = fields.Many2one(
        'saas_portal.database', 'Template', ondelete='restrict')
    demo = fields.Boolean('Install Demo Data')
    maximum_allowed_dbs_per_partner = fields.Integer(
        help='maximum allowed non-trial databases per customer', require=True, default=0)
    maximum_allowed_trial_dbs_per_partner = fields.Integer(
        help='maximum allowed trial databases per customer', require=True, default=0)

    max_users = fields.Char('Initial Max users',
                            default='0', help='leave 0 for no limit')
    total_storage_limit = fields.Integer(
        'Total storage limit (MB)', help='leave 0 for no limit')
    block_on_expiration = fields.Boolean(
        'Block clients on expiration', default=False)
    block_on_storage_exceed = fields.Boolean(
        'Block clients on storage exceed', default=False)

    def _get_default_lang(self):
        return self.env.user.lang

    def _default_tz(self):
        return self.env.user.tz

    lang = fields.Selection(scan_languages(), 'Language',
                            default=_get_default_lang)
    tz = fields.Selection(_tz_get, 'TimeZone', default=_default_tz)
    sequence = fields.Integer('Sequence')
    state = fields.Selection([('draft', 'Draft'), ('confirmed', 'Confirmed')],
                             'State', compute='_compute_get_state', store=True)
    expiration = fields.Integer(
        'Expiration (hours)', help='time to delete database. Use for demo')
    _order = 'sequence'
    grace_period = fields.Integer(
        'Grace period (days)', help='initial days before expiration')

    dbname_template = fields.Char(
        'DB Names', help='Used for generating client database domain name. Use %i for numbering. Ignore if you use manually created db names', placeholder='crm-%i.odoo.com')
    server_id = fields.Many2one('saas_portal.server', string='SaaS Server',
                                ondelete='restrict',
                                help='User this saas server or choose random')

    website_description = fields.Html('Website description')
    logo = fields.Binary('Logo')

    on_create = fields.Selection([
        ('login', 'Log into just created instance'),
    ], string="Workflow on create", default='login')
    on_create_email_template = fields.Many2one('mail.template',
                                               default=lambda self: self.env.ref('saas_portal.email_template_create_saas'))

    @api.multi
    @api.depends('template_id.state')
    def _compute_get_state(self):
        for plan in self:
            if plan.template_id.state == 'template':
                plan.state = 'confirmed'
            else:
                plan.state = 'draft'

    @api.multi
    def _new_database_vals(self, vals):
        self.ensure_one()
        vals['max_users'] = vals.get('max_users',
                                     self.max_users)
        vals['total_storage_limit'] = vals.get('total_storage_limit',
                                               self.total_storage_limit)
        vals['block_on_expiration'] = vals.get('block_on_expiration',
                                               self.block_on_expiration)
        vals['block_on_storage_exceed'] = vals.get('block_on_storage_exceed',
                                                   self.block_on_storage_exceed)
        return vals

    @api.multi
    def _prepare_owner_user_data(self, user_id):
        """
        Prepare the dict of values to update owner user data in client instalnce. This method may be
        overridden to implement custom values (making sure to call super() to establish
        a clean extension chain).
        """
        self.ensure_one()
        owner_user = self.env['res.users'].browse(user_id) or self.env.user
        owner_user_data = {
            'user_id': owner_user.id,
            'login': owner_user.login,
            'name': owner_user.name,
            'email': owner_user.email,
            'password_crypt': owner_user.password_crypt,
        }
        return owner_user_data

    @api.multi
    def _get_expiration(self, trial):
        self.ensure_one()
        trial_hours = trial and self.expiration
        initial_expiration_datetime = datetime.now()
        trial_expiration_datetime = (initial_expiration_datetime + timedelta(
            hours=trial_hours)).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        return trial and trial_expiration_datetime or initial_expiration_datetime.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

    @api.multi
    def create_new_database(self, **kwargs):
        return self._create_new_database(**kwargs)

    @api.multi
    def _create_new_database(self, dbname=None, client_id=None,
                             partner_id=None, user_id=None, notify_user=True,
                             trial=False, support_team_id=None, async=None):
        self.ensure_one()
        p_client = self.env['saas_portal.client']
        p_server = self.env['saas_portal.server']
        server = self.server_id
        if not server:
            server = p_server.get_saas_server()

        # server.action_sync_server()
        if not partner_id and user_id:
            user = self.env['res.users'].browse(user_id)
            partner_id = user.partner_id.id

        if not trial and self.maximum_allowed_dbs_per_partner != 0:
            db_count = p_client.search_count([('partner_id', '=', partner_id),
                                              ('state',
                                               '=', 'open'),
                                              ('plan_id',
                                               '=', self.id),
                                              ('trial', '=', False)])
            if db_count >= self.maximum_allowed_dbs_per_partner:
                raise MaximumDBException("Limit of databases for this plan is %(maximum)s reached" % {
                                         'maximum': self.maximum_allowed_dbs_per_partner})
        if trial and self.maximum_allowed_trial_dbs_per_partner != 0:
            trial_db_count = p_client.search_count([('partner_id', '=', partner_id),
                                                    ('state',
                                                     '=', 'open'),
                                                    ('plan_id',
                                                     '=', self.id),
                                                    ('trial', '=', True)])
            if trial_db_count >= self.maximum_allowed_trial_dbs_per_partner:
                raise MaximumTrialDBException("Limit of trial databases for this plan is %(maximum)s reached" % {
                                              'maximum': self.maximum_allowed_trial_dbs_per_partner})

        client_expiration = self._get_expiration(trial)
        vals = {'name': dbname or self.generate_dbname(),
                'server_id': server.id,
                'plan_id': self.id,
                'partner_id': partner_id,
                'trial': trial,
                'support_team_id': support_team_id,
                'expiration_datetime': client_expiration,
                }
        client = None
        if client_id:
            vals['client_id'] = client_id
            client = p_client.search(
                [('client_id', '=', client_id)])

        vals = self._new_database_vals(vals)

        if client:
            client.write(vals)
        else:
            client = p_client.create(vals)
        client_id = client.client_id

        owner_user_data = self._prepare_owner_user_data(user_id)

        state = {
            'd': client.name,
            'public_url': client.public_url,
            'e': client_expiration,
            'r': client.public_url + 'web',
            'h': client.host,
            'owner_user': owner_user_data,
            't': client.trial,
        }
        if self.template_id:
            state.update({'db_template': self.template_id.name})
        scope = ['userinfo', 'force_login', 'trial', 'skiptheuse']
        req, req_kwargs = server._request_server(path='/saas_server/new_database',
                                                 state=state,
                                                 client_id=client_id,
                                                 scope=scope,)
        res = requests.Session().send(req, **req_kwargs)
        if res.status_code != 200:
            raise Warning(_('Error on request: %s\nReason: %s \n Message: %s') % (
                req.url, res.reason, res.content))
        data = simplejson.loads(res.text)
        params = {
            'state': data.get('state'),
            'access_token': client.oauth_application_id._get_access_token(user_id, create=True),
        }
        url = '{url}?{params}'.format(url=data.get(
            'url'), params=werkzeug.url_encode(params))
        auth_url = url

        # send email if there is mail template record
        template = self.on_create_email_template
        if template and notify_user:
            # we have to have a user in this place (how to user without a user?)
            user = self.env['res.users'].browse(user_id)
            client.with_context(user=user).message_post_with_template(
                template.id, composition_mode='comment')

        client.send_params_to_client_db()
        # TODO make async call of action_sync_server here
        # client.server_id.action_sync_server()
        client.sync_client()

        return {'url': url,
                'id': client.id,
                'client_id': client_id,
                'auth_url': auth_url}

    @api.multi
    def generate_dbname(self, raise_error=True):
        self.ensure_one()
        if not self.dbname_template:
            if raise_error:
                raise exceptions.Warning(
                    _('Template for db name is not configured'))
            return ''
        sequence = self.env['ir.sequence'].get('saas_portal.plan')
        return self.dbname_template.replace('%i', sequence)

    @api.multi
    def create_template_button(self):
        return self.create_template()

    @api.multi
    def create_template(self, addons=None):
        self.ensure_one()
        state = {
            'd': self.template_id.name,
            'demo': self.demo and 1 or 0,
            'addons': addons or [],
            'lang': self.lang,
            'tz': self.tz,
            'is_template_db': 1,
        }
        client_id = self.template_id.client_id
        self.template_id.server_id = self.server_id

        req, req_kwargs = self.server_id._request_server(
            path='/saas_server/new_database', state=state, client_id=client_id)
        res = requests.Session().send(req, **req_kwargs)

        if not res.ok:
            raise Warning(_('Error on request: %s\nReason: %s \n Message: %s') %
                          (req.url, res.reason, res.content))
        try:
            data = simplejson.loads(res.text)
        except Exception as e:
            _logger.error(_('Error on parsing response: %s\n%s') %
                          ([req.url, req.headers, req.body], res.text))
            raise

        self.template_id.password = data.get('superuser_password')
        self.template_id.state = data.get('state')
        return data

    @api.multi
    def action_sync_server(self):
        for r in self:
            r.server_id.action_sync_server()
        return True

    @api.multi
    def edit_template(self):
        return self[0].template_id.edit_database()

    @api.multi
    def upgrade_template(self):
        return self[0].template_id.show_upgrade_wizard()

    @api.multi
    def delete_template(self):
        self.ensure_one()
        res = self.template_id.delete_database_server()
        return res


class SaasPortalPlanTopup (models.Model):
    _name = 'saas_portal.plan_topup'

    name = fields.Char('Topup name')
    summary = fields.Char('Summary')
    plan_id = fields.Many2one(
        'saas_portal.plan', 'Master Plan', ondelete='restrict')
    product_template_id = fields.Many2one(
        'saas_portal.database', 'Product', ondelete='restrict')