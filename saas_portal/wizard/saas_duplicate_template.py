from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.service import db
from odoo.tools import scan_languages
from odoo.exceptions import ValidationError


class SaasDuplicateTemplateWizard(models.TransientModel):
    _name = 'saas_portal.duplicate_template.wizard'
    _description = 'SaaS Portal Duplicate Template Wizard'

    @api.model
    def _get_template_id(self):
        return self._context.get('active_id', False)

    template_id = fields.Many2one(comodel_name="saas_portal.database", string="Template",
                                   required=True, ondelete="cascade", default=_get_template_id, auto_join=True)
    new_name = fields.Char(string="New name")
    lang = fields.Selection(scan_languages(), 'Language')

    @api.multi
    def duplicate_template(self):
        new_db = self.new_name
        if self.template_id:
            saas_portal_database = self.env['saas_portal.database']
            if saas_portal_database.search([('name', '=', new_db)]):
                raise ValidationError(
                    _("This database already exists: "
                      "'%s'") % new_db
                )
            db._drop_conn(self.env.cr, self.template_id.name)
            db.exp_duplicate_database(self.template_id.name, new_db)
            new_template = saas_portal_database.create({
                'name': new_db,
                'server_id': self.template_id.server_id.id,
                'state': 'template'
            })

            action = self.env.ref('saas_portal.action_templates').read()[0]
            if action:
                action['views'] = [(self.env.ref('saas_portal.view_databases_form').id, 'form')]
                action['res_id'] = new_template.ids[0]
            else:
                action = {'type': 'ir.actions.act_window_close'}
            return action
