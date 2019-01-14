from odoo import api, fields, models
from odoo.tools import scan_languages


class SaasClient(models.AbstractModel):
    """
    This model is used or inherited by modules as:  saas_portal.client and saas_server.client
    """
    _name = 'saas_base.client'
    _description = 'SaaS client instances base data'

    users_len = fields.Integer('Count users', readonly=True, help='Actual created internal users')
    max_users = fields.Char('Max users allowed', readonly=True, help='Overall internal user limit')
    file_storage = fields.Integer('File storage (MB)', readonly=True, help='Used file storage')
    db_storage = fields.Integer('DB storage (MB)', readonly=True, help='Used database storage')
    total_storage_limit = fields.Integer('Total storage limit (MB)', readonly=True, default=0,
                                         help='Overall storage limit')
    # Following fields where in saas_portal.client before
    total_storage = fields.Integer('Used storage (MB)', compute='_get_storage_client_sum', help='from Client')
    trial = fields.Boolean('Trial', help='indication of trial clients', default=False, readonly=True)
    client_primary_lang = fields.Selection(scan_languages(),
                                           'Instance primary language', readonly=False)

    expiration_datetime = fields.Datetime(string="Expiration")
    expired = fields.Boolean('Expired')

    @api.multi
    #  @api.depends('state')
    def _get_storage_client_sum(self):
        for record in self:
            record.total_storage = record.file_storage + record.db_storage
