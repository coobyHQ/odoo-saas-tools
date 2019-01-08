from odoo import models, fields


class ProductTemplateSaaS(models.Model):
    _inherit = 'product.template'

    is_saas = fields.Boolean('SaaS Product')
    saas_product_type = fields.Selection([
        ('base', 'Base'),
        ('topup', 'Topups')],
        string='SaaS Product Type')

    saas_base_type = fields.Selection([
        ('server', 'Base Server based'),
        ('container', 'Base Container based')],
        string='SaaS Base Type')

    saas_topup_type = fields.Selection([
        ('users', 'Additional Users'),
        ('storage', 'Additional Storage'),
        ('kube_pot', 'Additional Kubernetes Pots'),
        ('cert_le', 'Letsencrypt Certificate'),
        ('cert_own', 'Own commercial Certificate')],
        string='SaaS Topup Type')


    saas_default = fields.Boolean(
        'Is default',
        help='Use as default SaaS product on signup form')
    trial_allowed = fields.Boolean(
        'Trial instance is allowed',
        help='In webshop the form gets an extra Button "Trial"')
    on_create_email_template = fields.Many2one(
        'mail.template',
        string='credentials mail')

    saas_plan_id = fields.Many2one('saas_portal.plan',
                                   string='Related SaaS Plan',
                                   ondelete='restrict')

    # Todo ev. to delete, Makes no sense as one Product should relate to one plan.
    plan_ids = fields.One2many(
        'saas_portal.plan', 'product_tmpl_id',
        string='SaaS Plans',
        help='Create db per each selected plan - use the DB Names prefix setting in each selected plans')



class ProductAttributeSaaS(models.Model):
    _inherit = "product.attribute"

    saas_code = fields.Selection('_get_saas_codes')

    def _get_saas_codes(self):
        return [
                ('lang', 'Language')
                ]
