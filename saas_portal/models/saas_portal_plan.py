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


class SaasPortalPlan(models.Model):
    _name = 'saas_portal.plan'
    _description = 'SaaS Plan (templates)'
    _order = 'sequence'

    name = fields.Char('Plan', required=True)
    summary = fields.Char('Summary')
    template_id = fields.Many2one('saas_portal.database', 'DB Template',
                                  required=True, ondelete='restrict')
    demo = fields.Boolean('Install Demo Data')
    maximum_allowed_dbs_per_partner = fields.Integer(
        help='maximum allowed non-trial databases per customer', require=True, default=10)
    maximum_allowed_trial_dbs_per_partner = fields.Integer(
        help='maximum allowed trial databases per customer', require=True, default=2)

    max_users = fields.Integer('Initial Max users', default='0', help='leave 0 for no limit')
    max_storage = fields.Integer('Total storage limit (MB)',
                                      Default=200, help='leave 0 for no limit')
    block_on_expiration = fields.Boolean('Block clients on expiration', default=True)
    block_on_storage_exceed = fields.Boolean('Block clients when they reach the storage limit', default=True)

    def _get_default_lang(self):
        return self.env.user.lang

    def _default_tz(self):
        return self.env.user.tz

    lang = fields.Selection(scan_languages(), 'Language', default=_get_default_lang)
    tz = fields.Selection(_tz_get, 'TimeZone', default=_default_tz)
    sequence = fields.Integer('Sequence')
    state = fields.Selection([('draft', 'Draft'), ('confirmed', 'Confirmed')],
                             'State', compute='_compute_get_state', store=True)
    expiration = fields.Integer('Expiration (hours)', default=48, help='time to delete database. Use for trial')
    grace_period = fields.Integer('Grace period (days)', default=14, help='initial days before expiration')
    dbname_template = fields.Char('Default DB subdomain', help='Used for generating client database subdomain name. Use %i for numbering. '
                                  'Ignore if you use manually created db names', default='trial%i', placeholder='trial-crm-%i')
    branch_id = fields.Many2one('saas_portal.server_branch', string='SaaS Server Branch',
                                ondelete='restrict', required=True,
                                help='Use this Server Branch for this plan')
    server_id = fields.Many2one(related='branch_id.active_server', String='Active Server',
                                       help="Active Server for new instances")
    active_domain_name = fields.Char(related='branch_id.active_domain_name', string='Active Domain Name',
                                     help="Active Domain for new instances")
    domain = fields.Char(related='branch_id.active_server.domain', string='Server Domain', readonly=True)
    upgrade_path_ids = fields.Many2many('saas_portal.plan', 'saas_portal_plan_upgrade_rel', 'plan_id', 'upgrade_plan_id', string='Potential Plans To Upgrade To')
    downgrade_path_ids = fields.Many2many('saas_portal.plan', 'saas_portal_plan_downgrade_rel', 'plan_id', 'downgrade_plan_id', string='Potential Plans To Downgrade To')
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
        # vals['total_storage_limit'] = vals.get('total_storage_limit',
        #                                       self.total_storage_limit)
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
                             partner_id=None, user_id=None, notify_user=True, order_id=None,
                             trial=False, support_team_id=None, async=None, lang=None, template_db=None):
        self.ensure_one()
        p_client = self.env['saas_portal.client']
        p_server = self.env['saas_portal.server']

        server = False
        # 1 selecting the server to use
        if self.branch_id and self.branch_id.active_server:
            server = self.branch_id.active_server
        if not server:
            server = p_server.get_saas_server()

        # 2 checking of maximum_allowed_dbs_per_partner
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
        # 3 Setting of client_expiration
        client_expiration = self._get_expiration(trial)
        vals = {'subdomain': dbname or self.generate_dbname(),
                'server_id': server.id,
                'plan_id': self.id,
                'partner_id': partner_id,
                'trial': trial,
                'support_team_id': support_team_id,
                'expiration_datetime': client_expiration,
                }
        # 4 Choosing of Template DB
        if template_db:
            tmpl = self.env['saas_portal.database'].search([('name', '=', template_db), ('state', '=', 'template')], limit=1)
            if tmpl and tmpl.db_primary_lang:
                vals.update(client_primary_lang=tmpl.db_primary_lang)
        if 'client_primary_lang' not in vals and self.lang:
            vals.update(client_primary_lang=self.lang)
        client = None
        if client_id:
            vals['client_id'] = client_id
            client = p_client.search(
                [('client_id', '=', client_id)])

        # 5 Writing to client the database_vals (limits)
        vals = self._new_database_vals(vals)
        if client:
            client.write(vals)
        else:
            client = p_client.create(vals)
        client_id = client.client_id

        owner_user_data = self._prepare_owner_user_data(user_id)

        # 6 Syncing of client values
        state = {
            'd': client.name,
            'public_url': client.public_url,
            'e': client_expiration,
            'r': client.public_url + 'web',
            'h': client.host,
            'owner_user': owner_user_data,
            't': client.trial,
        }
        if lang:
            state.update(lang=lang)
            if template_db: state.update({'db_template': template_db})
        if self.template_id and 'db_template' not in state:
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

        # 7 send email if there is mail template record
        template = self.on_create_email_template
        if template and notify_user:
            # we have to have a user in this place (how to use without a user?)
            user = self.env['res.users'].browse(user_id)
            client.with_context(user=user).message_post_with_template(
                template.id, composition_mode='comment')

        # 8 send_params_to_client_db
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
                    _('Template for db subdomain is not configured'))
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
