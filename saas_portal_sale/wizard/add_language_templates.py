from odoo import models, fields, api, SUPERUSER_ID
from odoo.tools.translate import _
import odoo
from odoo.service import db
from odoo.tools import scan_languages, load_language
from odoo.exceptions import ValidationError


class SaasAddLangTemplatesWizard(models.TransientModel):
    _name = 'saas_portal.add_language_templates.wizard'
    _description = 'Add Language Templates Wizard'

    @api.model
    def _get_plan_id(self):
        return self._context.get('active_id', False)

    @api.model
    def _get_template_id(self):
        template_id = self.env['saas_portal.plan'].browse(self._context.get('active_id', False)).template_id
        if not template_id:
            raise ValidationError(
                _("The plan must have a template database!")
            )
        return template_id.id

    plan_id = fields.Many2one(comodel_name="saas_portal.plan", string="Plan",
                                  required=True, ondelete="cascade", default=_get_plan_id)
    template_id = fields.Many2one(comodel_name="saas_portal.database", string="Template",
                                   required=True, ondelete="cascade", default=_get_template_id, auto_join=True)
    prefix = fields.Char(string="Prefix", help="Prefix for database name (gets added before language code)", required=False)
    suffix = fields.Char(string="Suffix", help="Suffix for database name (gets added after language code)", required=False)
    language_ids = fields.Many2many('res.lang', 'saas_plan_add_template_lang_rel', 'wizard_id', 'lang_id', 'Languages', domain=['|', ('active', '=', True), ('active', '=', False)])

    @api.multi
    def registry(self, dbname, new=False, **kwargs):
        self.ensure_one()
        m = odoo.modules.registry.Registry
        return m.new(dbname, **kwargs)

    @api.multi
    def add_language_templates(self):
        if not self.language_ids:
            raise ValidationError(
                _("Please select language(s)!")
            )
        if self.template_id and self.language_ids:
            saas_portal_database = self.env['saas_portal.database']
            # first check if there are existing databases
            for language in self.language_ids:
                dbname = (self.prefix or '') + language.iso_code + (self.suffix or '') + '.' + self.template_id.domain
                if saas_portal_database.search([('name', '=', dbname)]):
                    raise ValidationError(
                        _("This database already exists: "
                          "'%s'") % dbname
                    )
            if self.plan_id and self.plan_id.product_tmpl_id:
                for attr in self.plan_id.product_tmpl_id.attribute_line_ids:
                    if attr.attribute_id and attr.attribute_id.saas_code == 'lang':
                        lang_attr = attr
                        break
            for language in self.language_ids:
                subdomain = (self.prefix or '') + language.iso_code + (self.suffix or '')
                dbname = "%s.%s" % (subdomain, self.template_id.domain)
                db._drop_conn(self.env.cr, self.template_id.name)
                db.exp_duplicate_database(self.template_id.name, dbname)
                new_template = saas_portal_database.create({
                    'subdomain': subdomain,
                    'server_id': self.template_id.server_id.id,
                    'db_primary_lang': language.code,
                    'plan_ids': [(4, self.plan_id.id)],
                    'state': 'template'
                })
                with self.registry(dbname).cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, self._context)
                    # load a new language:
                    load_language(env.cr, language.code)
                    # set this language for all partner records:
                    for partner in env['res.partner'].search([]):
                        partner.lang = language.code
                    # if website is installed, also load the language
                    if env['ir.module.module'].search([('name', '=', 'website')]).state in ('installed', 'to upgrade'):
                        website = env["website"].get_current_website()
                        wiz = env["base.language.install"].create({"lang": language.code})
                        wiz.website_ids = website
                        wiz.lang_install()
                        res_lang_id = env['res.lang'].search([('code', '=', language.code)])
                        if res_lang_id:
                            # make it a default website language
                            website.default_lang_id = res_lang_id
                if lang_attr:
                    attr_value = self.env['product.attribute.value'].search([('name', '=', language.name), ('attribute_id', '=', lang_attr.attribute_id.id)])
                    if attr_value:
                        attr_value.template_ids = [(4, new_template.id)]
                        self.plan_id.product_tmpl_id.write({
                            'attribute_line_ids': [(1, lang_attr.id, {
                                'value_ids': [(4, attr_value.id)]
                            })]
                        })
                    else:
                        lang_attr.value_ids = [(0, 0, {
                                            'name': language.name,
                                            'attribute_id': lang_attr.attribute_id.id,
                                            'saas_lang': language.code,
                                            'template_ids': [(4, new_template.id)]
                                        })]

            action = {'type': 'ir.actions.act_window_close'}
            return action
