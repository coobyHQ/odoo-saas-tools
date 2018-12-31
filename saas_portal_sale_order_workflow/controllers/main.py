from odoo.http import request
from odoo import http, SUPERUSER_ID
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.website_sale.controllers.main import WebsiteSaleForm
from odoo.exceptions import ValidationError
from odoo.addons.base.ir.ir_qweb.fields import nl2br
import json
import logging

_logger = logging.getLogger(__name__)


class SaasCreateInstanceAfterValidating(WebsiteSale):

    def get_saas_domain(self):
        config = request.env['ir.config_parameter']
        full_param = 'saas_portal.base_saas_domain'
        base_saas_domain = config.sudo().get_param(full_param)
        return base_saas_domain

    # ------------------------------------------------------
    # Extra step to add dbname
    # ------------------------------------------------------
    @http.route(['/shop/extra_info'], type='http', auth="public", website=True)
    def extra_info(self, **post):

        # Check that this option is activated
        extra_step = request.env.ref('website_sale.extra_info_option')
        if not extra_step.active:
            return request.redirect("/shop/payment")

        # check that cart is valid
        order = request.website.sale_get_order()
        redirection = self.checkout_redirection(order)
        if redirection:
            return redirection

        # if form posted
        if 'post_values' in post:
            values = {}
            for field_name, field_value in post.items():
                if field_name in request.env['sale.order']._fields and field_name.startswith('x_'):
                    values[field_name] = field_value
            if values:
                order.write(values)
            return request.redirect("/shop/payment")

        if not post.get('base_saas_domain', False):
            base_saas_domain = self.get_saas_domain()
            post['base_saas_domain'] = base_saas_domain

        values = {
            'website_sale_order': order,
            'post': post,
            'base_saas_domain': base_saas_domain,
            'escape': lambda x: x.replace("'", r"\'"),
            'partner': order.partner_id.id,
            'order': order,
        }

        return request.render("website_sale.extra_info", values)

    @http.route('/shop/payment/validate', type='http', auth="public", website=True)
    def payment_validate(self, transaction_id=None, sale_order_id=None, **post):
        """ Method that should be called by the server when receiving an update
        for a transaction. State at this point :

         - UDPATE ME
        """
        if transaction_id is None:
            tx = request.website.sale_get_transaction()
        else:
            tx = request.env['payment.transaction'].browse(transaction_id)

        if sale_order_id is None:
            order = request.website.sale_get_order()
        else:
            order = request.env['sale.order'].sudo().browse(sale_order_id)
            assert order.id == request.session.get('sale_last_order_id')

        if not order or (order.amount_total and not tx):
            return request.redirect('/shop')

        if (not order.amount_total and not tx) or tx.state in ['pending', 'done', 'authorized']:
            if (not order.amount_total and not tx):
                # Orders are confirmed by payment transactions, but there is none for free orders,
                # (e.g. free events), so confirm immediately
                order.with_context(send_email=True).action_confirm()
        elif tx and tx.state == 'cancel':
            # cancel the quotation
            order.action_cancel()

        # clean context and session, then redirect to the confirmation page
        request.website.sale_reset()
        if tx and tx.state == 'draft':
            return request.redirect('/shop')

        # create a new saas client
        if order and order.order_line.mapped('product_id').filtered(
                lambda product: product.saas_plan_id != False):
            plan_id = 1
            dbname = order.saas_dbname
            if plan_id and dbname:
                redirect = '/saas_portal/add_new_client'
                redirect_url = '%s?dbname=%s&plan_id=%s' % (
                    redirect, dbname, plan_id
                )
                return request.redirect(redirect_url)

        return request.redirect('/shop/confirmation')

class WebsiteSaleForm(WebsiteSaleForm):

    @http.route('/website_form/shop.sale.order.dbname', type='http', auth="public", methods=['POST'], website=True)
    def website_form_saleorder(self, **kwargs):
        model_record = request.env.ref('sale.model_sale_order')
        try:
            data = self.extract_data(model_record, kwargs)
        except ValidationError as e:
            return json.dumps({'error_fields': e.args[0]})

        order = request.website.sale_get_order()
        if data['record']:
            order.write(data['record'])

        if 'dbname' in kwargs:
            order.write({'saas_dbname': kwargs['dbname']})

        if data['custom']:
            values = {
                'body': nl2br(data['custom']),
                'model': 'sale.order',
                'message_type': 'comment',
                'no_auto_thread': False,
                'res_id': order.id,
            }
            request.env['mail.message'].sudo().create(values)

        if data['attachments']:
            self.insert_attachment(model_record, order.id, data['attachments'])

        return json.dumps({'id': order.id})

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
