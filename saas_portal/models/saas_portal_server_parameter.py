from odoo import fields, models


class SaasPortalServerParam(models.Model):
    _name = 'saas_portal.server_parameter'
    _description = 'SaaS Server/Parameter'
    _rec_name = 'name'
    _order = 'sequence'

    name = fields.Char('Name', required=True)
    sequence = fields.Integer('Sequence', default=10, help="Determine the display order")
    server_id = fields.Many2one('saas_portal.server', string='Servers')
    set_id = fields.Many2one('saas_portal.server_parameter_set', string='Parameter Set')
    parameter = fields.Char('Parameter')
    description = fields.Char('Description')
    default = fields.Char('Default Value')
    value = fields.Char('Value')
    docker_image = fields.Char(string='Docker image')
    server_branch_id = fields.Many2one('saas_portal.server_branch', string='Server Branches')
    parameter_type = fields.Selection([('image', 'Image'),
                                      ('odoo', 'Odoo'),
                                      ('persistent', 'Persistent'),
                                      ('addons', 'Addons folder'),
                                      ('service', 'Service'),
                                      ('ingress', 'Ingress'),
                                      ('postgresql', 'Postgresql'),
                                      ('other', 'Other'),
                                       ],
                                      'Parameter Type', default='', track_visibility='onchange')

    # server_branch_id = fields.Many2one('saas_portal.server_branch', string='Server Branches')


class SaasPortalServerParamSet(models.Model):
    _name = 'saas_portal.server_parameter_set'
    _description = 'SaaS Server/Parameter Set'
    _rec_name = 'name'
    _order = 'sequence'

    name = fields.Char('Name', required=True)
    sequence = fields.Integer('Sequence', default=10, help="Determine the display order")
    parameter_ids = fields.One2many('saas_portal.server_parameter', 'set_id', string='Parameter')
    description = fields.Char('Description')
    server_branch_ids = fields.Many2many('saas_portal.server_branch', 'parameter_ids', string='Server Branches')
    parameter_type = fields.Selection([('image', 'Image'),
                                       ('application', 'Application'),
                                       ('storage', 'Storage / volume'),
                                       ('storage_container', 'Storage container / volume'),
                                       ('database', 'Database Container/Server'),
                                       ('webserver', 'Webserver Container/NGINX'),
                                       ('identity-server', 'Identity Server/Container'),
                                       ('postgresql', 'Postgresql'),
                                       ('other', 'Other'),
                                       ],
                                      'Parameter Set Type', default='', track_visibility='onchange')
