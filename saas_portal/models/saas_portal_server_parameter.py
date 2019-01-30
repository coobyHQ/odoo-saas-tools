from odoo import fields, models


class SaasPortalServerParam(models.Model):
    _name = 'saas_portal.server_parameter'
    _description = 'SaaS Server/Parameter'
    _rec_name = 'name'

    name = fields.Char('Name', required=True)
    set_id = fields.Many2one('saas_portal.server_parameter_set', string='Parameter Set')
    parameter = fields.Char('Parameter')
    description = fields.Char('Description')
    value = fields.Char('Value')
    server_id = fields.Many2one('saas_portal.server', 'parameter_ids', string='Servers')
    server_branch_id = fields.Many2one('saas_portal.server_branch', 'parameter_ids', string='Server Branches')


class SaasPortalServerParamSet(models.Model):
    _name = 'saas_portal.server_parameter_set'
    _description = 'SaaS Server/Parameter Set'
    _rec_name = 'name'

    name = fields.Char('Name', required=True)
    parameter = fields.Char('Parameter')
    description = fields.Char('Description')
    default = fields.Char('Default Value')
    docker_image = fields.Char(string='Docker image')
    # server_branch_id = fields.Many2one('saas_portal.server_branch', 'parameter_ids', string='Server Branches')
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
