from odoo import SUPERUSER_ID
from odoo import api
from odoo import exceptions
from odoo import models, fields


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        """ Override to hide saas modules from normal users and only show it to the superuser. """
        res = super(IrModuleModule, self).search(args, offset=0, limit=None, order=order, count=False)
        if self._uid != SUPERUSER_ID:
            res = res.filtered(lambda m: 'saas' not in m.name and 'auth_oauth' not in m.name and 'access_limit_records_number' not in m.name)
        return res
