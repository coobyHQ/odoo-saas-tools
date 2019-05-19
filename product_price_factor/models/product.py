from odoo import models, fields, api
import odoo.addons.decimal_precision as dp


class ProductTemplateAttributeValue(models.Model):
    _inherit = "product.template.attribute.value"

    price_factor = fields.Float(
        'Price Factor', digits=dp.get_precision('Product Price'), default=1.0)


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.multi
    def price_compute(self, price_type, uom=False, currency=False, company=False):
        # TDE FIXME: delegate to template or not ? fields are reencoded here ...
        # compatibility about context keys used a bit everywhere in the code
        if not uom and self._context.get('uom'):
            uom = self.env['uom.uom'].browse(self._context['uom'])
        if not currency and self._context.get('currency'):
            currency = self.env['res.currency'].browse(self._context['currency'])

        products = self
        if price_type == 'standard_price':
            # standard_price field can only be seen by users in base.group_user
            # Thus, in order to compute the sale price from the cost for users not in this group
            # We fetch the standard price as the superuser
            products = self.with_context(force_company=company and company.id or self._context.get('force_company', self.env.user.company_id.id)).sudo()

        prices = dict.fromkeys(self.ids, 0.0)
        for product in products:
            prices[product.id] = product[price_type] or 0.0
            if price_type == 'list_price':
                for value in product.product_template_attribute_value_ids.filtered(lambda r: r.attribute_id in [a.attribute_id for a in product.attribute_value_ids]):
                    prices[product.id] = (prices[product.id] + value.price_extra) * value.price_factor
                # we need to add the price from the attributes that do not generate variants
                # (see field product.attribute create_variant)
                if self._context.get('no_variant_attributes_price_extra'):
                    # we have a list of price_extra that comes from the attribute values, we need to sum all that
                    prices[product.id] += sum(self._context.get('no_variant_attributes_price_extra'))

            if uom:
                prices[product.id] = product.uom_id._compute_price(prices[product.id], uom)

            # Convert from current user company currency to asked one
            # This is right cause a field cannot be in more than one currency
            if currency:
                prices[product.id] = product.currency_id._convert(
                    prices[product.id], currency, product.company_id, fields.Date.today())

        return prices


class ProductTemplateAttributeLine(models.Model):
    _inherit = "product.template.attribute.line"
    _order = 'sequence'

    def _default_sequence(self):
        # without this function there was a bug when attributes were created
        # from Product Variants tab. If several attributes were created without pushing the save button
        # sequence got the same value for their attribute lines. And if there was no lines before
        # sequence got False for the first attribute
        num = self.search_count([]) + 1
        return num

    sequence = fields.Integer(
        'Sequence', help="Determine the display order", required=True, default=_default_sequence)
