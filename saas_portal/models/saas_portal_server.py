import simplejson
import werkzeug
import requests
import random
from odoo import api, exceptions, fields, models
from odoo.tools.translate import _

import logging
_logger = logging.getLogger(__name__)


@api.multi
def _compute_host(self):
    base_saas_domain = self.env['ir.config_parameter'].sudo().get_param('saas_portal.base_saas_domain')
    for r in self:
        host = r.name
        domain = r.domain or base_saas_domain
        if domain and '.' not in r.name:
            host = '%s.%s' % (r.name, domain)
        r.host = host

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

    _inherit = ['mail.thread']
    _inherits = {'oauth.application': 'oauth_application_id'}

    @api.model
    def _get_domain(self):
        return  self.env['ir.config_parameter'].sudo().get_param('saas_portal.base_saas_domain') or ''

    # Attention names is used for database name, another field name_txt as Title was created,
    name_txt = fields.Char('Name', required=True)
    name = fields.Char('Database name', required=True)
    summary = fields.Char('Summary')
    branch_id = fields.Many2one('saas_portal.server_branch', string='SaaS Server Branch',
                                ondelete='restrict')
    branch_aux_ids = fields.Many2many('saas_portal.server_branch', 'aux_server_ids', string='SaaS Server Branches')
    oauth_application_id = fields.Many2one(
        'oauth.application', 'OAuth Application', required=True, ondelete='cascade')
    domain = fields.Char('Server SaaS domain', help='Set base domain name for this SaaS server', default=_get_domain)
    sequence = fields.Integer('Sequence')
    # What is active for, better to have state (LUH)?
    active = fields.Boolean('Active', default=True)
    state = fields.Selection([('draft', 'Draft'),
                              ('running', 'Running'),
                              ('running_full', 'Running Full'),
                              ('running_err', 'Running with Error'),
                              ('running_failed', 'Running Failed'),
                              ('stopped', 'Stopped'),
                              ('cancelled', 'Cancelled'),
                              ],
                             'State', default='draft',
                             track_visibility='onchange')
    branch_type = fields.Selection(related='branch_id.branch_type', string='SaaS Server Type', readonly=True)
    branch_product_type = fields.Selection(related='branch_id.product_type', string='Branch Product Type', readonly=True)
    server_type = fields.Selection([
        ('application', 'Application'),
        ('storage', 'Storage / volume'),
        ('storage_container', 'Storage container / volume'),
        ('database', 'Database Container/Server'),
        ('webserver', 'Webserver Container/NGINX'),
        ('other', 'Other Product')],
        string='Server type', help='Which service the SaaS Server is providing')
    odoo_version = fields.Selection(related='branch_id.odoo_version', string='Odoo version', readonly=True,
                                    help='Which Odoo version is hosted')
    container_url = fields.Char('Container URL', help="URL to the used container")
    container_name = fields.Char('Container Name')
    container_image = fields.Char('Container Image')

    max_client = fields.Integer('Max #of Client DB`s', default=100)
    # Todo compute number
    number_of_clients = fields.Integer('# of Client DB`s', readonly=True)
    request_scheme = fields.Selection(
        [('http', 'http'), ('https', 'https')], 'Scheme', default='http', required=True)
    verify_ssl = fields.Boolean(
        'Verify SSL', default=True, help="verify SSL certificates for server-side HTTPS requests, just like a web browser")
    request_port = fields.Integer('Request Port', default=80)
    client_ids = fields.One2many('saas_portal.client', 'server_id', string='Clients')
    local_host = fields.Char('Local host', help='local host or ip address of server for server-side requests')
    local_port = fields.Char('Local port', help='local tcp port of server for server-side requests')
    local_request_scheme = fields.Selection([('http', 'http'), ('https', 'https')], 'Scheme', default='http', required=True)
    host = fields.Char('Host', compute=_compute_host)
    # Todo use of password is not yet clear?
    password = fields.Char('Default Superadmin password')
    clients_host_template = fields.Char('Template for clients host names',
                                        help='The possible dynamic parts of the host names are: {dbname}, {base_saas_domain}, {base_saas_domain_1}')

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
        scheme = scheme or self.request_scheme
        port = port or self.request_port
        scope = scope or ['userinfo', 'force_login', 'trial', 'skiptheuse']
        scope = ' '.join(scope)
        client_id = client_id or self.env['oauth.application'].generate_client_id(
        )
        params = {
            'scope': scope,
            'state': simplejson.dumps(state),
            'redirect_uri': '{scheme}://{saas_server}:{port}{path}'.format(scheme=scheme, port=port, saas_server=self.host, path=path),
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
        scheme = scheme or self.local_request_scheme or self.request_scheme
        host = self.local_host or self.host
        port = port or self.local_port or self.request_port
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
                               headers={'host': self.host})
        req_kwargs = {'verify': self.verify_ssl}
        return req.prepare(), req_kwargs

    @api.multi
    def action_redirect_to_server(self):
        r = self[0]
        url = '{scheme}://{saas_server}:{port}{path}'.format(
            scheme=r.request_scheme, saas_server=r.host, port=r.request_port, path='/web')
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'name': 'Redirection',
            'url': url
        }

    @api.model
    def action_sync_server_all(self):
        p_client = self.env['saas_portal.client']

        self.search([]).action_sync_server()
        p_client.search([]).storage_usage_monitoring()

    @api.multi
    def action_sync_server(self, updating_client_ID=None):
        for server in self:
            state = {
                'd': server.name,
                'client_id': server.client_id,
                'updating_client_ID': updating_client_ID,
            }
            req, req_kwargs = server._request_server(
                path='/saas_server/sync_server', state=state, client_id=server.client_id)
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
            for r in data:
                r['server_id'] = server.id
                client = server.env['saas_portal.client'].with_context(
                    active_test=False).search([('client_id', '=', r.get('client_id'))])
                if not client:
                    database = server.env['saas_portal.database'].search(
                        [('client_id', '=', r.get('client_id'))])
                    if database:
                        database.write(r)
                        continue
                    client = server.env['saas_portal.client'].create(r)
                else:
                    client.write(r)
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
