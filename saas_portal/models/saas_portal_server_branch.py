import simplejson
import werkzeug
import requests
import random
from odoo import api, exceptions, fields, models
from odoo.exceptions import ValidationError

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


class SaasPortalServerBranch(models.Model):
    _name = 'saas_portal.server_branch'
    _description = 'SaaS Server/Product Branch'
    _rec_name = 'name'

    _inherit = ['mail.thread', 'mail.activity.mixin']
    _inherits = {'oauth.application': 'oauth_application_id'}

    @api.model
    def _get_domain(self):
        return self.env['ir.config_parameter'].sudo().get_param('saas_portal.base_saas_domain') or ''

    @api.multi
    @api.depends('app_server_ids', 'app_server_ids.max_client', 'app_server_ids.number_of_clients', 'app_server_ids.active')
    def _get_active_server(self):
        for branch in self:
            next_active_server = False
            for server in self.env['saas_portal.server'].search([('branch_id', '=', branch.id)], order='sequence'):
                if server.number_of_clients < server.max_client:
                    next_active_server = server
                    break
            if next_active_server:
                branch.active_server = next_active_server.id

    name = fields.Char('Branch name', required=True)
    active_server = fields.Many2one('saas_portal.server', 'Active Server', required=False,
                                    compute='_get_active_server', store=True,
                                    help="Active Server for new instances")
    active_domain_name = fields.Char(related='active_server.domain', string='Active Domain Name', required=False,
                                     help="Active Domain for new instances")
    summary = fields.Char('Summary')
   # oauth_application_id = fields.Many2one(
   #     'oauth.application', 'OAuth Application', required=True, ondelete='cascade')
    app_server_ids = fields.One2many('saas_portal.server', 'branch_id', string='App Servers')
    aux_server_ids = fields.Many2many('saas_portal.server', 'branch_aux_ids', string='Auxiliary Servers', ondelete='restrict')
    parameter_ids = fields.One2many('saas_portal.server_parameter', 'server_branch_id', string='SaaS Server Parameter',
                                    ondelete='restrict')
    plan_ids = fields.One2many('saas_portal.plan', 'branch_id', string='Related SaaS Plans')
    client_ids = fields.One2many(related='app_server_ids.client_ids', string='Clients')
    sequence = fields.Integer('Sequence')
    # What is active for, better to have state (LUH)?
    active = fields.Boolean('Active', default=True)
    state = fields.Selection([('draft', 'Draft'),
                              ('running', 'Running'),
                              ('stopped', 'Stopped'),
                              ('cancelled', 'Cancelled'),
                              ],
                             'State', default='draft',
                             track_visibility='onchange')
    branch_type = fields.Selection([
        ('server', 'Server based'),
        ('container', 'Container Application'),
        ('container_kube', 'Container Kubernetes based')],
        string='SaaS Server Type')
    product_type = fields.Selection([
        ('odoo', 'Odoo Server based'),
        ('flectra', 'Flectra ERP'),
        ('other-erp', 'Other ERP'),
        ('other', 'Other Product')],
        string='Product type', help='Which product the SaaS Server is hosting')
    odoo_version = fields.Selection([
        ('V11', 'Odoo V 11'),
        ('V12', 'Odoo V 12'),
        ('V13', 'Odoo V 13')],
        string='Odoo version', help='Which Odoo version is hosted')

    server_url = fields.Char('Container URL', help="URL to the used container")
    server_name = fields.Char('Container Name')
    rancher_project = fields.Char('Rancher Project')
    rancher_namespace = fields.Char('Rancher Namespace')

    # Todo compute number
    number_of_clients = fields.Integer('# of Client DB`s', readonly=True)
    request_scheme = fields.Selection(
        [('http', 'http'), ('https', 'https')], 'Scheme', default='https', required=True)
    verify_ssl = fields.Boolean(
        'Verify SSL', default=True, help="verify SSL certificates for server-side HTTPS requests, just like a web browser")
    request_port = fields.Integer('Request Port', default=443)
    # Todo not necessary in branch?
    local_host = fields.Char('Local host', help='local host or ip address of server for server-side requests')
    local_port = fields.Char('Local port', default=443, help='local tcp port of server for server-side requests')
    local_request_scheme = fields.Selection(
        [('http', 'http'), ('https', 'https')], 'Scheme', default='https', required=True)
    host = fields.Char('Host', compute=_compute_host)
    # Todo use of password is not yet clear?
    password = fields.Char('Default Superadmin password')
    clients_host_template = fields.Char('Template for clients host names',
                                        help='The possible dynamic parts of the host names are: {dbname}, {base_saas_domain}, {base_saas_domain_1}')

