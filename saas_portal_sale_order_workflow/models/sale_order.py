from odoo import fields, models

import logging
_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    saas_dbname = fields.Char('SaaS Database name')
