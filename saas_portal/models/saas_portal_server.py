import simplejson
import werkzeug
import requests
import random
from odoo import api, exceptions, fields, models
from odoo.tools.translate import _

import logging
_logger = logging.getLogger(__name__)

"""
todo  action_create_server will ask for master password only.-->
 https: // erppeek.readthedocs.org / en / latest / api.html  # erppeek.Client.create_database-->
button string = "Create Server"
name = "%(action_create_server)d"
type = "action" class ="oe_highlight" states="draft" / >
"""


class SaasPortalServer(models.Model):
    _name = 'saas_portal.server'
    _description = 'SaaS Server / Container'
    _rec_name = 'name_txt'
    _order = 'sequence'

    _inherit = ['mail.thread']
    _inherits = {'oauth.application': 'oauth_application_id'}

    @api.model
    def _get_domain(self):
        return self.env['ir.config_parameter'].sudo().get_param('saas_portal.base_saas_domain') or ''

    @api.multi
    @api.depends('subdomain', 'domain')
    def _compute_db_name(self):
        for record in self:
            subdomain = record.subdomain
            domain = record.domain
            record.name = "%s.%s" % (subdomain, domain)

    @api.multi
    @api.depends('branch_id')
    def _get_default_max_nr_of_client(self):
        for record in self:
            default_max_nr = record.branch_id.default_max_client or 100
            record.max_client = default_max_nr

    # Todo does not work yet
    @api.multi
    def _check_state_server_full(self):
        print(self.max_client, self.number_of_clients)
        if self.state == 'synced':
            max_client = self.max_client
            number_of_clients = self.number_of_clients
            if number_of_clients >= max_client:
                self.state = 'synced_full'
            elif number_of_clients < max_client:
                self.state = 'synced'
            return

    @api.multi
    @api.depends('client_ids')
    def _get_number_of_clients(self):
        for server in self:
            server.number_of_clients = len(server.client_ids.filtered(lambda c: c.state == 'open') or [])

    # Attention names is used for database name, another field name_txt as Title was created,
    name_txt = fields.Char('Name', required=True)
    name = fields.Char('Database name', readonly=True, compute='_compute_db_name', store=True)
    subdomain = fields.Char('Sub Domain', required=True)
    domain = fields.Char(related='branch_id.branch_domain', string='Server SaaS domain', readonly=True)
    branch_prefix = fields.Char(related='branch_id.prefix', string='Branch Domain Prefix', readonly=True)
    branch_id = fields.Many2one('saas_portal.server_branch', string='SaaS Server Branch', ondelete='restrict')
    branch_aux_ids = fields.Many2many('saas_portal.server_branch', 'aux_server_ids', string='SaaS Server Branches')
    parameter_ids = fields.One2many('saas_portal.server_parameter', 'server_id',  string='SaaS Server Parameter',
                                    ondelete='restrict')
    oauth_application_id = fields.Many2one('oauth.application', 'OAuth Application', required=True, ondelete='cascade')
    summary = fields.Char('Summary')
    sequence = fields.Integer('Sequence')
    # What is active for, better to have state (LUH)?
    active = fields.Boolean('Active', default=True)
    state = fields.Selection([('draft', 'Draft'),
                              ('synced', 'Synced'),
                              ('synced_full', 'Synced/Full'),
                              ('sync_error', 'Sync Error'),
                              ('client_error', 'Client Error'),
                              ('stopped', 'Stopped'),
                              ('cancelled', 'Cancelled'),
                              ],
                             'State', default='draft',
                             track_visibility='onchange')
    sync_error_message = fields.Char('Sync Error Message')
    branch_type = fields.Selection(related='branch_id.branch_type', string='SaaS Server Type', readonly=True)
    branch_product_type = fields.Selection(related='branch_id.product_type', string='Branch Product Type', readonly=True)
    server_type = fields.Selection([
        ('application', 'Application'),
        ('storage', 'Storage / volume'),
        ('storage_container', 'Storage container / volume'),
        ('database', 'Database Container/Server'),
        ('webserver', 'Webserver Container/NGINX'),
        ('identity-server', 'Identity Server/Container'),
        ('other', 'Other Product')],
        string='Server type', help='Which service this server is providing', default='application', required=True)
    server_function = fields.Selection([('client', 'Clients'),
                                        ('quarantine', 'Quarantine'),
                                        ('template', 'Templates'),
                                        ('mixed', 'Clients & Templates'),
                                        ('other', 'Other'),
                                        ],
                                       'Server Function', default='client', track_visibility='onchange')
    odoo_version = fields.Selection(related='branch_id.odoo_version', string='Odoo version', readonly=True,
                                    help='Which Odoo version is hosted')
    container_url = fields.Char('Container URL', help="URL to the used container")
    container_name = fields.Char('Container Name')
    container_image = fields.Char('Container Image')

    max_client = fields.Integer('Max #of Client DB`s', default=_get_default_max_nr_of_client)
    number_of_clients = fields.Integer('# of Client DB`s', readonly=True, compute='_get_number_of_clients', store=True)
    client_ids = fields.One2many('saas_portal.client', 'server_id', string='Client instances')
    database_ids = fields.One2many('saas_portal.database', 'server_id', string='Template Databases')
    # RPC Server side
    local_host = fields.Char('Local host', help='localhost or ip address of server for server-side requests')
    local_port = fields.Char('Local port', default=8069, help='local tcp port of server for server-side requests')
    local_request_scheme = fields.Selection(related='branch_id.local_request_scheme', string='Scheme', readonly=True)
    # RPC Portal side
    request_scheme = fields.Selection(related='branch_id.request_scheme', string='Scheme', readonly=True)
    verify_ssl = fields.Boolean(related='branch_id.verify_ssl', string='Verify SSL', readonly=True,
                                help="verify SSL certificates for server-side HTTPS requests, just like a web browser")
    request_port = fields.Integer(related='branch_id.request_port', string='Request Port', readonly=True)
    # Todo use of password is not yet clear?
    password = fields.Char(related='branch_id.password', string='Default Superadmin password', readonly=True)

    @api.multi
    def name_get(self):
        res = []
        for record in self:
            res.append((record.id, '%s [%s]' % (record.name_txt, record.name)))
        return res

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        domain = args or []
        domain += [
            '|',
            ('name', operator, name),
            ('name_txt', operator, name),
        ]
        return self.search(domain, limit=limit).name_get()

    @api.model
    def create(self, vals):
        record = super(SaasPortalServer, self).create(vals)
        record.oauth_application_id._get_access_token(create=True)
        return record

    @api.multi
    def _request_params(self, path='/web', scheme=None,
                        port=None, state=None, scope=None, client_id=None):
        self.ensure_one()
        if not state:
            state = {}
        scheme = scheme or self.request_scheme or 'http'
        port = port or self.request_port or 80
        scope = scope or ['userinfo', 'force_login', 'trial', 'skiptheuse']
        scope = ' '.join(scope)
        client_id = client_id or self.env['oauth.application'].generate_client_id(
        )
        params = {
            'scope': scope,
            'state': simplejson.dumps(state),
            'redirect_uri': '{scheme}://{saas_server}:{port}{path}'.format(scheme=scheme, port=port, saas_server=self.name, path=path),
            'response_type': 'token',
            'client_id': client_id,
        }
        return params

    @api.multi
    def _request(self, **kwargs):
        self.ensure_one()
        params = self._request_params(**kwargs)
        url = '/oauth2/auth?%s' % werkzeug.url_encode(params)
        return url

    @api.multi
    def _request_server(self, path=None, scheme=None, port=None, **kwargs):
        self.ensure_one()
        scheme = scheme or self.local_request_scheme or self.request_scheme or 'http'
        host = self.local_host or self.name
        port = port or self.local_port or self.request_port or 80
        params = self._request_params(**kwargs)
        access_token = self.oauth_application_id.sudo()._get_access_token(create=True)
        params.update({
            'token_type': 'Bearer',
            'access_token': access_token,
            'expires_in': 3600,
        })
        url = '{scheme}://{host}:{port}{path}'.format(
            scheme=scheme, host=host, port=port, path=path)
        req = requests.Request('GET', url, data=params,
                               headers={'host': self.name})
        req_kwargs = {'verify': self.verify_ssl}
        return req.prepare(), req_kwargs
        # server.state = 'sync_error'

    @api.multi
    def action_redirect_to_server(self):
        r = self[0]
        url = '{scheme}://{saas_server}:{port}{path}'.format(
            scheme=r.request_scheme or 'http', saas_server=r.name, port=r.request_port or 80, path='/web')
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'name': 'Redirection',
            'url': url
        }

    @api.multi
    def action_sync_server_all(self):
        self.search([]).action_sync_server()
        self.env['saas_portal.client'].search([]).storage_usage_monitoring()

    @api.multi
    def action_sync_server(self, updating_client_ID=None):
        for server in self:
            if server.server_type == 'application':
                state = {
                    'd': server.name,
                    'client_id': server.client_id,
                    'updating_client_ID': updating_client_ID,
                }
                req, req_kwargs = server._request_server(
                    path='/saas_server/sync_server', state=state, client_id=server.client_id)
                res = requests.Session().send(req, **req_kwargs)

                if not res.ok:
                    server.state = 'sync_error'
                    msg = _('Reason: %s \n Message: %s') % (res.reason, res.content)
                    server.sync_error_message = msg
                    raise Warning(msg)
                try:
                    data = simplejson.loads(res.text)
                except Exception as e:
                    msg = 'Error on parsing response: %s\n%s' % ([req.url, req.headers, req.body], res.text)
                    _logger.error(msg)
                    server.state = 'sync_error'
                    server.sync_error_message = msg
                    raise
                for r in data:
                    r['server_id'] = server.id
                    client = server.env['saas_portal.client'].with_context(
                        active_test=False).search([('client_id', '=', r.get('client_id'))])
                    if not client:
                        database = server.env['saas_portal.database'].search([('client_id', '=', r.get('client_id'))])
                        if database:
                            database.write(r)
                            continue
                        client = server.env['saas_portal.client'].create(r)
                    else:
                        client.write(r)
                server.state = 'synced'
                self._check_state_server_full
            return None
        else:
            return None

    @api.model
    def get_saas_server(self):
        p_server = self.env['saas_portal.server']
        saas_server_list = p_server.sudo().search([])
        return saas_server_list[random.randint(0, len(saas_server_list) - 1)]


class OauthApplication(models.Model):
    _inherit = 'oauth.application'

    client_id = fields.Char('Database UUID')
    last_connection = fields.Char(compute='_compute_get_last_connection',
                                  string='Last Connection', size=64)
    server_db_ids = fields.One2many(
        'saas_portal.server', 'oauth_application_id',
        string='Server Database')
    template_db_ids = fields.One2many(
        'saas_portal.database', 'oauth_application_id',
        string='Template Database')
    client_db_ids = fields.One2many(
        'saas_portal.client', 'oauth_application_id',
        string='Client Database')

    @api.multi
    def _compute_get_last_connection(self):
        for r in self:
            oat = self.env['oauth.access_token']
            to_search = [('application_id', '=', r.id)]
            access_tokens = oat.search(to_search)
            if access_tokens:
                access_token = access_tokens[0]
                r.last_connection = access_token.user_id.login_date
