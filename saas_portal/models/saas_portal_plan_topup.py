from odoo import api, exceptions, fields, models


class SaasPortalPlanTopup (models.Model):
    _name = 'saas_portal.plan_topup'

    name = fields.Char('Topup name')
