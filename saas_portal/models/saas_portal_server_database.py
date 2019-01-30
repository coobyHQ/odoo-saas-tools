import simplejson
import werkzeug
import requests
import random
from odoo import api, exceptions, fields, models
from odoo.tools.translate import _

import logging
_logger = logging.getLogger(__name__)


class SaasPortalServerDatabase(models.Model):
    _name = 'saas_portal.server_database'
    _description = 'SaaS Server / Container'
    _rec_name = 'name'

    _inherit = ['saas_portal.database']


    active = fields.Boolean('Active', default=True)
    server_state = fields.Selection([('draft', 'Draft'),
                              ('running', 'Running'),
                              ('running_full', 'Running Full'),
                              ('running_err', 'Running with Error'),
                              ('running_failed', 'Running Failed'),
                              ('stopped', 'Stopped'),
                              ('cancelled', 'Cancelled'),
                              ],
                             'Server State', default='draft',
                             track_visibility='onchange')

    max_client = fields.Integer('Max #of Client DB`s', default=100)
    number_of_clients = fields.Integer('# of Client DB`s', readonly=True, compute='_get_number_of_clients', store=True)

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

