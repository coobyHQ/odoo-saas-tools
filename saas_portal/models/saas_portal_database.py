import simplejson
import requests
from odoo import api, exceptions, fields, models
from odoo.tools.translate import _
from odoo.tools import scan_languages

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


class SaasPortalDatabase(models.Model):
    _name = 'saas_portal.database'
    _description = 'Saas database instances'
    _inherits = {'oauth.application': 'oauth_application_id'}

    name = fields.Char('Database name', readonly=False)
    oauth_application_id = fields.Many2one(
        'oauth.application', 'OAuth Application',
        required=True, ondelete='cascade')
    # Todo needs to be readonly = False for now to work, should be taken from client form.
    server_id = fields.Many2one(
        'saas_portal.server', ondelete='restrict',
        string='Server', readonly=False)
    server_db_name = fields.Char(related='server_id.name', string='Database name', readonly=True)
    server_type = fields.Selection(related='server_id.server_type', string='SaaS Server Type', readonly=True)
    product_type = fields.Selection(related='server_id.product_type', string='Product type', readonly=True,
                                    help='Which product the SaaS Server is hosting')
    odoo_version = fields.Selection(related='server_id.odoo_version', string='Odoo version', readonly=True,
                                    help='Which Odoo version is hosted')
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
    db_primary_lang = fields.Selection(scan_languages(), 'Database primary language')
    public_url = fields.Char(compute='_compute_public_url')
    # Todo use of password is not yet clear?
    password = fields.Char('Default Database Password')

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

    @api.multi
    def duplicate_template_button(self):
        view_id = self.env.ref('saas_portal.saas_plan_duplicate_template_wizard_form')
        context = self._context.copy()
        context.update(active_id=self.id)
        return {
            'name': _('Duplicate A Template'),
            'type': 'ir.actions.act_window',
            'res_model': 'saas_portal.duplicate_template.wizard',
            'view_mode': 'form',
            'view_type': 'form',
            'views': [(view_id.id, 'form')],
            'target': 'new',
            'context': context
        }

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
