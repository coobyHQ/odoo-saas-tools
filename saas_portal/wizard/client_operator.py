import requests
import random
import string
from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class SaasOperatorWizard(models.TransientModel):
    _name = 'saas.config'
    _description = 'SaaS Operator wizard'

    def _default_database_ids(self):
        return self._context.get('active_ids')

    action = fields.Selection([('edit', 'Edit'),
                               ('upgrade', 'Configure'),
                               ('delete', 'Delete')],
                                'Action')
    database_ids = fields.Many2many(
        'saas_portal.client', string='Database', default=_default_database_ids)
    update_addons_list = fields.Boolean('Update Addon List', default=True)
    update_addons = fields.Char('Update Addons', size=256)
    install_addons = fields.Char('Install Addons', size=256)
    uninstall_addons = fields.Char('Uninstall Addons', size=256)
    access_owner_add = fields.Char('Grant access to Owner')
    access_remove = fields.Char(
        'Restrict access',
        help='Restrict access for all users except super-user.\nNote, that ')
    fix_ids = fields.One2many('saas.config.fix', 'config_id', 'Fixes')
    limit_line_ids = fields.One2many(
        'saas.config.limit_number_of_records_line', 'config_id', 'Limit line')
    param_ids = fields.One2many('saas.config.param', 'config_id', 'Parameters')
    description = fields.Text('Result')

    @api.multi
    def execute_action(self):
        res = False
        method = '%s_database' % self.action
        if hasattr(self, method):
            res = getattr(self, method)()
        return res

    @api.multi
    def delete_database(self):
        return self.database_ids.delete_database()

    @api.multi
    def upgrade_database(self):
        self.ensure_one()
        obj = self[0]
        payload = {
            # TODO: add configure mail server option here
            'update_addons_list': (obj.update_addons_list or ''),
            'update_addons': obj.update_addons.split(',') if obj.update_addons else [],
            'install_addons': obj.install_addons.split(',') if obj.install_addons else [],
            'uninstall_addons': obj.uninstall_addons.split(',') if obj.uninstall_addons else [],
            'access_owner_add': obj.access_owner_add.split(',') if obj.access_owner_add else [],
            'access_remove': obj.access_remove.split(',') if obj.access_remove else [],
            'fixes': [[x.model, x.method] for x in obj.fix_ids],
            'params': [{'key': x.key,
                        'value': x.value,
                        'hidden': x.hidden} for x in obj.param_ids],
            'limit_nuber_of_records': [{
                'model': x.model,
                'max_records': x.max_records,
                'domain': x.domain} for x in obj.limit_line_ids],
        }
        res = self.database_ids.upgrade(payload=payload)

        res_str = '\n\n'.join(res)
        obj.write({'description': res_str})
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'saas.config',
            'res_id': obj.id,
            'target': 'new'
        }

    @api.model
    def do_upgrade_database(self, payload, database_record):
        state = {
            'data': payload,
        }
        req, req_kwargs = database_record.server_id._request_server(
            path='/saas_server/upgrade_database',
            client_id=database_record.client_id,
            state=state,
        )
        res = requests.Session().send(req, **req_kwargs)
        if not res.ok:
            raise Warning(_('Reason: %s \n Message: %s') %
                          (res.reason, res.content))
        return res.text


class SaasConfigFix(models.TransientModel):
    _name = 'saas.config.fix'

    model = fields.Char('Model', required=1, size=64)
    method = fields.Char('Method', required=1, size=64)
    config_id = fields.Many2one('saas.config', 'Config')


class SaasConfigLimitNumberOfRecords(models.TransientModel):
    _name = 'saas.config.limit_number_of_records_line'

    model = fields.Char('Model', required=1, size=64)
    domain = fields.Char('Domain', required=1, size=64, default='[]')
    max_records = fields.Integer(string='Maximum Records', required=1)
    config_id = fields.Many2one('saas.config', 'Config')


class SaasConfigParam(models.TransientModel):
    _name = 'saas.config.param'

    def _get_keys(self):
        return [
            # this parameter is obsolete.Use access_limit_records_number module
            ('saas_client.max_users', 'Max Users (obsolete)'),
            ('saas_client.suspended', 'Suspended'),
            ('saas_client.total_storage_limit', 'Total storage limit'),
        ]

    key = fields.Selection(selection=_get_keys,
                           string='Key', required=1, size=64)
    value = fields.Char('Value', required=1, size=64)
    config_id = fields.Many2one('saas.config', 'Config')
    hidden = fields.Boolean('Hidden parameter', default=True)

