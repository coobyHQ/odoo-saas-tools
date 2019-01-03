from odoo import fields
from odoo import models


class SaasClient(models.AbstractModel):
    _name = 'saas_base.client'
    _description = 'Saas clint database instances'

    users_len = fields.Integer('Count users', readonly=True, help='Actual created internal users')
    max_users = fields.Char('Max users allowed', readonly=True, help='Overall internal user limit')
    file_storage = fields.Integer('File storage (MB)', readonly=True, help='Used file storage')
    db_storage = fields.Integer('DB storage (MB)', readonly=True, help='Used database storage')

    total_storage_limit = fields.Integer('Total storage limit (MB)', readonly=True, default=0,
                                         help='Overall storage limit')
    trial = fields.Boolean('Trial', help='indication of trial clients', default=False, readonly=True)
