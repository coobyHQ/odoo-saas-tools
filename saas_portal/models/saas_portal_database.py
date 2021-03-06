import simplejson
import requests
from odoo import api, exceptions, fields, models
from odoo.tools.translate import _
from odoo.tools import scan_languages

import logging
_logger = logging.getLogger(__name__)


class SaasPortalDatabase(models.Model):
    # gets inherited by saas_portal.client
    _name = 'saas_portal.database'
    _description = 'Saas database instances'
    _inherits = {'oauth.application': 'oauth_application_id'}
    _order = 'identifier'

    @api.model
    def _get_default_name_txt(self):
        return "%s %s" % (self.name or '', self.db_primary_lang or '')

    @api.multi
    @api.depends('subdomain', 'domain')
    def _compute_db_name(self):
        for record in self:
            subdomain = record.subdomain
            domain = record.domain
            record.name = "%s.%s" % (subdomain, domain)

    name = fields.Char('Database name', compute='_compute_db_name', store=True)
    name_txt = fields.Char('Name', required=True, default=_get_default_name_txt)
    identifier = fields.Char('Identifier', readonly=True, default=lambda self: _('New'))
    summary = fields.Char('Summary', compute='_get_compose_summary', store=True)
    oauth_application_id = fields.Many2one(
        'oauth.application', 'OAuth Application',
        required=True, ondelete='cascade')
    # Todo needs to be readonly = False for now to work, should be taken from client form.
    server_id = fields.Many2one('saas_portal.server', ondelete='restrict',
                                string='Server', readonly=False, required=True)
    server_db_name = fields.Char(related='server_id.name', string='Server Database name', readonly=True)
    subdomain = fields.Char('Sub Domain', required=True)
    domain = fields.Char(related='server_id.name', string='Server Domain', readonly=True)
    server_type = fields.Selection(related='server_id.server_type', string='SaaS Server Type', readonly=True)
    product_type = fields.Selection(related='server_id.branch_product_type', string='Product type', readonly=True,
                                    help='Which product the SaaS Server is hosting')
    odoo_version = fields.Selection(related='server_id.odoo_version', string='Odoo version', readonly=True,
                                    help='Which Odoo version is hosted')
    state = fields.Selection([('draft', 'New'),
                              ('open', 'Running'),
                              ('open_err', 'Running with Error'),
                              ('open_failed', 'Running Failed'),
                              ('cancelled', 'Cancelled'),
                              ('pending', 'Pending'),
                              ('deleted', 'Deleted'),
                              ('template', 'Template'),
                              ],
                             'State', default='draft',
                             track_visibility='onchange')
    db_type = fields.Selection([('client', 'Client'),
                               ('template', 'Template'),
                               ('other', 'Other'),
                                ],
                               'DB Type', default='client', track_visibility='onchange')

    host = fields.Char(related='server_id.name', string='Host', readonly=True)
    db_primary_lang = fields.Selection(scan_languages(), 'Database primary language')
    public_url = fields.Char(compute='_compute_public_url')
    # Todo use of password is not yet clear?
    password = fields.Char('Default Database Password')
    plan_ids = fields.Many2many('saas_portal.plan', 'saas_portal_database_templates', 'template_id', 'plan_id', string='SaaS Plans')

    _sql_constraints = [('name_unique', 'unique(name)',
                         'Database name already exists.')]

    @api.multi
    def name_get(self):
        res = []
        for record in self:
            if record.db_primary_lang:
                res.append((record.id, '%s [%s]' % (record.name, record.db_primary_lang)))
            else:
                res.append((record.id, record.name))
        return res

    @api.multi
    def _get_compose_summary(self):
        for record in self:
            subdomain = record.subdomain or ''
            lang = record.db_primary_lang or ''
            summary = "Template %s, %s" % (subdomain, lang)
            record.summary = summary

    @api.model
    def create(self, vals):
        if vals.get('identifier', _('New')) == _('New'):
            vals['identifier'] = self.env['ir.sequence'].next_by_code('saas_portal.database') or _('New')
        if vals.get('name') and not vals.get('subdomain', False) and not vals.get('name_txt', False):
            vals['subdomain'] = vals['name']
            vals['name_txt'] = vals['name']
        return super(SaasPortalDatabase, self).create(vals)

    @api.multi
    def _compute_public_url(self):
        for record in self:
            scheme = record.server_id.request_scheme
            db_name = record.name
            port = record.server_id.request_port
            public_url = "%s://%s" % (scheme, db_name)
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

    @api.multi
    def delete_template(self):
        self.ensure_one()
        res = self.delete_database_server(force_delete=True)
        return res

    @api.multi
    def login_to_db(self):
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
