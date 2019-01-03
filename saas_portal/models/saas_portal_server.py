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
    base_saas_domain = self.env['ir.config_parameter'].sudo(
    ).get_param('saas_portal.base_saas_domain')
    for r in self:
        host = r.name
        if base_saas_domain and '.' not in r.name:
            host = '%s.%s' % (r.name, base_saas_domain)
        r.host = host


class SaasPortalServer(models.Model):
    _name = 'saas_portal.server'
    _description = 'SaaS Server'
    _rec_name = 'name'

    _inherit = ['mail.thread']
    _inherits = {'oauth.application': 'oauth_application_id'}

    name = fields.Char('Database name', required=True)
    oauth_application_id = fields.Many2one(
        'oauth.application', 'OAuth Application', required=True, ondelete='cascade')
    sequence = fields.Integer('Sequence')
    active = fields.Boolean('Active', default=True)
    request_scheme = fields.Selection(
        [('http', 'http'), ('https', 'https')], 'Scheme', default='http', required=True)
    verify_ssl = fields.Boolean(
        'Verify SSL', default=True, help="verify SSL certificates for server-side HTTPS requests, just like a web browser")
    request_port = fields.Integer('Request Port', default=80)
    client_ids = fields.One2many(
        'saas_portal.client', 'server_id', string='Clients')
    local_host = fields.Char(
        'Local host', help='local host or ip address of server for server-side requests')
    local_port = fields.Char(
        'Local port', help='local tcp port of server for server-side requests')
    local_request_scheme = fields.Selection(
        [('http', 'http'), ('https', 'https')], 'Scheme', default='http', required=True)
    host = fields.Char('Host', compute=_compute_host)
    odoo_version = fields.Char('Odoo version', readonly=True)
    password = fields.Char()
    clients_host_template = fields.Char('Template for clients host names',
                                        help='The possible dynamic parts of the host names are: {dbname}, {base_saas_domain}, {base_saas_domain_1}')

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


class SaasPortalDatabase(models.Model):
    _name = 'saas_portal.database'
    _description = 'Saas database instances'
    _inherits = {'oauth.application': 'oauth_application_id'}

    name = fields.Char('Database name', readonly=False)
    oauth_application_id = fields.Many2one(
        'oauth.application', 'OAuth Application',
        required=True, ondelete='cascade')
    server_id = fields.Many2one(
        'saas_portal.server', ondelete='restrict',
        string='Server', readonly=True)
    state = fields.Selection([('draft', 'New'),
                              ('open', 'Running'),
                              ('cancelled', 'Cancelled'),
                              ('pending', 'Pending'),
                              ('deleted', 'Deleted'),
                              ('template', 'Template'),
                              ],
                             'State', default='draft',
                             track_visibility='onchange')
    host = fields.Char('Host', compute='_compute_host')
    public_url = fields.Char(compute='_compute_public_url')
    password = fields.Char()

    @api.multi
    def _compute_host(self):
        base_saas_domain = self.env['ir.config_parameter'].sudo(
        ).get_param('saas_portal.base_saas_domain')
        base_saas_domain_1 = '.'.join(base_saas_domain.rsplit('.', 2)[-2:])
        name_dict = {
            'base_saas_domain': base_saas_domain,
            'base_saas_domain_1': base_saas_domain_1,
        }
        for record in self:
            if record.server_id.clients_host_template:
                name_dict.update({'dbname': record.name})
                record.host = record.server_id.clients_host_template.format(
                    **name_dict)
            else:
                _compute_host(self)

    @api.multi
    def _compute_public_url(self):
        for record in self:
            scheme = record.server_id.request_scheme
            host = record.host
            port = record.server_id.request_port
            public_url = "%s://%s" % (scheme, host)
            if scheme == 'http' and port != 80 or scheme == 'https' and port != 443:
                public_url = public_url + ':' + str(port)
            record.public_url = public_url + '/'

    @api.multi
    def _backup(self):
        '''
        call to backup database
        '''
        self.ensure_one()

        state = {
            'd': self.name,
            'client_id': self.client_id,
        }

        req, req_kwargs = self.server_id._request_server(
            path='/saas_server/backup_database', state=state, client_id=self.client_id)
        res = requests.Session().send(req, **req_kwargs)
        _logger.info('backup database: %s', res.text)
        if not res.ok:
            raise Warning(_('Reason: %s \n Message: %s') %
                          (res.reason, res.content))
        data = simplejson.loads(res.text)
        if not isinstance(data[0], dict):
            raise Warning(data)
        if data[0]['status'] != 'success':
            warning = data[0].get(
                'message', _('Could not backup database; please check your logs'))
            raise Warning(warning)
        return True

    @api.multi
    def action_sync_server(self):
        for record in self:
            record.server_id.action_sync_server()

    @api.model
    def _proceed_url(self, url):
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'name': 'Redirection',
            'url': url
        }

    @api.multi
    def _request_url(self, path):
        r = self[0]
        state = {
            'd': r.name,
            'host': r.host,
            'public_url': r.public_url,
            'client_id': r.client_id,
        }
        url = r.server_id._request(
            path=path, state=state, client_id=r.client_id)
        return url

    @api.multi
    def _request(self, path):
        url = self._request_url(path)
        return self._proceed_url(url)

    @api.multi
    def edit_database(self):
        """Obsolete. Use saas_portal.edit_database widget instead"""
        for database_obj in self:
            return database_obj._request('/saas_server/edit_database')

    @api.multi
    def delete_database(self):
        for database_obj in self:
            return database_obj._request('/saas_server/delete_database')

    @api.multi
    def upgrade(self, payload=None):
        config_obj = self.env['saas.config']
        res = []

        if payload is not None:
            # maybe use multiprocessing here
            for database_obj in self:
                res.append(config_obj.do_upgrade_database(
                    payload.copy(), database_obj))
        return res

    @api.multi
    def delete_database_server(self, **kwargs):
        self.ensure_one()
        return self._delete_database_server(**kwargs)

    @api.multi
    def _delete_database_server(self, force_delete=False):
        for database in self:
            state = {
                'd': database.name,
                'client_id': database.client_id,
            }
            if force_delete:
                state['force_delete'] = 1
            req, req_kwargs = database.server_id._request_server(
                path='/saas_server/delete_database',
                state=state, client_id=database.client_id)
            res = requests.Session().send(req, **req_kwargs)
            _logger.info('delete database: %s', res.text)
            if res.status_code != 500:
                database.state = 'deleted'

    @api.multi
    def show_upgrade_wizard(self):
        obj = self[0]
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'saas.config',
            'target': 'new',
            'context': {
                'default_action': 'upgrade',
                'default_database': obj.name
            }
        }
