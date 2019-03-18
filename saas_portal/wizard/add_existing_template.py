import requests
import random
import string
from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.tools import scan_languages
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class SaasPortalAddExistingDatabase(models.TransientModel):
    """
    Model to add an existing template db
    """
    _name = 'saas_portal.add_existing_template'

    @api.model
    def _get_default_name_txt(self):
        return "%s %s" % (self.subdomain or '', self.db_primary_lang or '')

    subdomain = fields.Char(string='Subdomain', required=False)
    name_txt = fields.Char('Name', required=True, default=_get_default_name_txt)
    server_id = fields.Many2one('saas_portal.server', string='Server', required=True)
    domain = fields.Char(related='server_id.name', string='Server Domain', readonly=True)
    db_primary_lang = fields.Selection(scan_languages(), 'Database primary language')
    plan_id = fields.Many2one('saas_portal.plan', string='Add To Plan')
    password = fields.Char(required=True)

    @api.multi
    def add(self):
        new_db = self.subdomain + '.' + self.server_id.domain
        saas_portal_database = self.env['saas_portal.database']
        if saas_portal_database.search([('name', '=', new_db)]):
            raise ValidationError(
                _("This database already exists: "
                  "'%s'") % new_db
            )
        vals = {
            'subdomain': self.subdomain,
            'name_txt': self.name_txt,
            'server_id': self.server_id.id,
            'state': 'template',
            'db_type': 'template',
            'db_primary_lang': self.db_primary_lang,
            'password': self.password,
        }
        if self.plan_id:
            vals.update(plan_ids=[(4, self.plan_id.id)])

        new_template = saas_portal_database.create(vals)
        if self.plan_id and not self.plan_id.template_id:
            self.plan_id.template_id = new_template.id

        return {'type': 'ir.actions.act_window_close'}
