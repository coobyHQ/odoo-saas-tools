import requests
import random
import string
from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class SaasPortalAddExistingDatabase(models.TransientModel):
    """
    Model to add an existing template db
    """
    _name = 'saas_portal.add_existing_template'

    name = fields.Char(string='Subdomain', required=True)
    server_id = fields.Many2one('saas_portal.server', string='Server', required=True)
    plan_id = fields.Many2one('saas_portal.plan', string='Add To Plan')
    password = fields.Char(required=True)

    @api.multi
    def add(self):
        new_db = self.name + '.' + self.server_id.domain
        saas_portal_database = self.env['saas_portal.database']
        if saas_portal_database.search([('name', '=', new_db)]):
            raise ValidationError(
                _("This database already exists: "
                  "'%s'") % new_db
            )
        new_template = saas_portal_database.create({
            'subdomain': self.name,
            'server_id': self.server_id.id,
            'state': 'template',
            'db_type': 'template',
            'password': self.password
        })

        return {'type': 'ir.actions.act_window_close'}
