from odoo import api, exceptions, fields, models

import logging
_logger = logging.getLogger(__name__)


class SaasPortalServerBranch(models.Model):
    _name = 'saas_portal.server_branch'
    _description = 'SaaS Server/Product Branch'
    _rec_name = 'name'

    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.model
    def _get_domain(self):
        return self.env['ir.config_parameter'].sudo().get_param('saas_portal.base_saas_domain') or ''

    @api.multi
    @api.depends('app_server_ids')
    def _get_number_of_clients(self):
        for branch in self:
            sum_total = 0
            for line in branch.app_server_ids:
                sum_total += line.number_of_clients
            branch.update({
                'number_of_clients': sum_total
            })

    # Todo fix  Expected singleton: saas_portal.server_branch(5, 6)
    @api.multi
    @api.depends('app_server_ids')
    def _get_state_of_servers(self):
        for branch in self:
            for line in branch.app_server_ids:
                if line.state == 'synced':
                    self.state = 'synced'
                elif line.state == 'sync_error':
                    self.state = 'sync_error'
                elif line.state == 'client_error':
                    self.state = 'client_error'
                else:
                    return

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
    prefix = fields.Char('Branch domain Prefix', required=True)
    branch_domain = fields.Char('Branch domain', help='Set base domain name for this Branch',
                                default=_get_domain, required=True)
    active_server = fields.Many2one('saas_portal.server', 'Active Server', required=False,
                                        compute='_get_active_server', store=True,
                                        help="Active Server for new instances")
    active_domain_name = fields.Char(related='active_server.domain', string='Active Domain Name', required=False,
                                     help="Active Domain for new instances")
    summary = fields.Char('Summary')
    app_server_ids = fields.One2many('saas_portal.server', 'branch_id', string='App Servers')
    aux_server_ids = fields.Many2many('saas_portal.server', 'branch_aux_ids', string='Auxiliary Servers', ondelete='restrict')
    parameter_ids = fields.Many2many('saas_portal.server_parameter_set', 'server_branch_ids', string='SaaS Server Parameter',
                                      ondelete='restrict')
    plan_ids = fields.One2many('saas_portal.plan', 'branch_id', string='Related SaaS Plans')
    # Todo only clients from one server are shown
    client_ids = fields.One2many(related='app_server_ids.client_ids', string='Clients')
    sequence = fields.Integer('Sequence')
    # What is active for, better to have state (LUH)?
    active = fields.Boolean('Active', default=True)
    state = fields.Selection([('draft', 'Draft'),
                              ('synced', 'Synced'),
                              ('sync_error', 'Sync Error'),
                              ('client_error', 'Client Error'),
                              ('stopped', 'Stopped'),
                              ('cancelled', 'Cancelled'),
                              ],
                             'State', default='draft', track_visibility='onchange')
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
        ('V11', 'Odoo V11'),
        ('V12', 'Odoo V12'),
        ('V13', 'Odoo V13')],
        string='Odoo version', help='Which Odoo version is hosted')

    server_url = fields.Char('Container URL', help="URL to the used container")
    server_name = fields.Char('Container Name')
    rancher_project = fields.Char('Rancher Project')
    rancher_namespace = fields.Char('Rancher Namespace')
    default_max_client = fields.Integer('Default Max #of Client DB`s', default=100)
    number_of_clients = fields.Integer('# of Client DB`s', readonly=True, compute='_get_number_of_clients', store=True)
    request_scheme = fields.Selection([('http', 'http'), ('https', 'https')], 'Scheme', default='https', required=True)
    verify_ssl = fields.Boolean(
        'Verify SSL', default=True, help="verify SSL certificates for server-side HTTPS requests, just like a web browser")
    request_port = fields.Integer('Request Port', default=443)
    local_host = fields.Char('Local host', help='local host or ip address of server for server-side requests')
    local_port = fields.Char('Local port', help='local tcp port of server for server-side requests')
    local_request_scheme = fields.Selection([('http', 'http'), ('https', 'https')], 'Scheme', default='https', required=True)
    # Todo use of password is not yet clear?
    password = fields.Char('Default Superadmin password')
