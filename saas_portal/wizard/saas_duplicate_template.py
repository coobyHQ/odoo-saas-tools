from odoo import models, fields, api, SUPERUSER_ID
from odoo.tools.translate import _
import odoo
from odoo.service import db
from odoo.tools import scan_languages, load_language
from odoo.exceptions import ValidationError


class SaasDuplicateTemplateWizard(models.TransientModel):
    _name = 'saas_portal.duplicate_template.wizard'
    _description = 'SaaS Portal Duplicate Template Wizard'

    @api.model
    def _get_template_id(self):
        return self._context.get('active_id', False)

    template_id = fields.Many2one(comodel_name="saas_portal.database", string="Template",
                                   required=True, ondelete="cascade", default=_get_template_id, auto_join=True)
    template_domain = fields.Char(related='template_id.domain', store=True, string='Domain', readonly=True)
    new_name = fields.Char(string="New subdomain name")
    lang = fields.Selection(scan_languages(), 'Language')

    @api.multi
    def registry(self, new=False, **kwargs):
        self.ensure_one()
        m = odoo.modules.registry.Registry
        return m.new(self.new_name + '.' + self.template_id.domain, **kwargs)

    @api.multi
    def duplicate_template(self):
        new_db = self.new_name + '.' + self.template_id.domain
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
                'subdomain': self.new_name,
                'server_id': self.template_id.server_id.id,
                'db_primary_lang': self.lang,
                'state': 'template',
                'db_type': 'template'
            })
            if self.lang:
                with self.registry().cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, self._context)
                    # load a new language:
                    load_language(env.cr, self.lang)
                    # set this language for all partner records:
                    for partner in env['res.partner'].search([]):
                        partner.lang = self.lang
                    # if website is installed, also load the language
                    if env['ir.module.module'].search([('name', '=', 'website')]).state in ('installed', 'to upgrade'):
                        website = env["website"].get_current_website()
                        wiz = env["base.language.install"].create({"lang": self.lang})
                        wiz.website_ids = website
                        wiz.lang_install()
                        res_lang_id = env['res.lang'].search([('code', '=', self.lang)])
                        if res_lang_id:
                            # make it a default website language
                            website.default_lang_id = res_lang_id

            action = self.env.ref('saas_portal.action_templates').read()[0]
            if action:
                action['views'] = [(self.env.ref('saas_portal.view_databases_form').id, 'form')]
                action['res_id'] = new_template.ids[0]
            else:
                action = {'type': 'ir.actions.act_window_close'}
            return action
