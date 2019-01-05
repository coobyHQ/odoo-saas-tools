from odoo.http import request
from odoo import http, SUPERUSER_ID
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.website_sale.controllers.main import WebsiteSaleForm
from odoo.addons.saas_portal.controllers.main import SaasPortal
from odoo.exceptions import ValidationError
from odoo.addons.base.ir.ir_qweb.fields import nl2br
from odoo.addons.saas_base.exceptions import MaximumDBException, MaximumTrialDBException
from urllib.parse import urlencode
import werkzeug
import json
import logging

_logger = logging.getLogger(__name__)


class SaasPortalOrder(SaasPortal):

    @http.route(['/saas_portal/add_new_client'], type='http', auth='public', website=True)
    def add_new_client(self, redirect_to_signup=False, **post):
        uid = request.session.uid
        if not uid:
            url = '/web/signup' if redirect_to_signup else '/web/login'
            redirect = str('/saas_portal/add_new_client?' + urlencode(post))
            query = {'redirect': redirect}
            return http.local_redirect(path=url, query=query)

        dbname = self.get_full_dbname(post.get('dbname'))
        user_id = request.session.uid
        partner_id = None
        if user_id:
            user = request.env['res.users'].browse(user_id)
            partner_id = user.partner_id.id
        plan = self.get_plan(int(post.get('plan_id', 0) or 0))
        trial = bool(post.get('trial', False))
        order_id = post.get('order_id')
        try:
            res = plan.create_new_database(dbname=dbname,
                                           user_id=user_id,
                                           partner_id=partner_id,
                                           trial=trial,
                                           order_id=order_id)
        except MaximumDBException:
            _logger.info("MaximumDBException")
            url = request.env['ir.config_parameter'].sudo().get_param('saas_portal.page_for_maximumdb', '/')
            return werkzeug.utils.redirect(url)
        except MaximumTrialDBException:
            _logger.info("MaximumTrialDBException")
            url = request.env['ir.config_parameter'].sudo().get_param('saas_portal.page_for_maximumtrialdb', '/')
            return werkzeug.utils.redirect(url)

        return werkzeug.utils.redirect(res.get('url'))


class SaasCreateInstanceAfterValidating(WebsiteSale):

    def get_saas_domain(self):
        config = request.env['ir.config_parameter']
        full_param = 'saas_portal.base_saas_domain'
        base_saas_domain = config.sudo().get_param(full_param)
        return base_saas_domain

    def get_topup_info(self, order, plan, client):
        additional_invoice_lines = []
        users = int(plan.max_users)
        storage = int(plan.total_storage_limit)
        for topup in plan.topup_ids:
            order_lines = order.order_line.filtered(lambda line: line.product_id.id == topup.product_tmpl_id.id)
            if order_lines:
                for line in order_lines:
                    if topup.topup_users:
                        users += int(topup.topup_users * line.product_uom_qty)
                    if topup.topup_storage:
                        storage += int(topup.topup_storage * line.product_uom_qty)
                    if topup.contract_template_id and client and client.contract_id:
                        for inv_line in topup.contract_template_id.recurring_invoice_line_ids:
                            additional_invoice_lines.append({
                                'analytic_account_id': client.contract_id and client.contract_id.id or False,
                                'product_id': inv_line.product_id.id,
                                'name': inv_line.name,
                                'quantity': inv_line.quantity * line.product_uom_qty,
                                'uom_id': inv_line.uom_id.id,
                                'automatic_price': inv_line.automatic_price,
                                'price_unit': inv_line.price_unit,
                            })
        return users, storage, additional_invoice_lines

    def upgrade_client_with_topup(self, client, plan_id, order_id):
        plan = request.env['saas_portal.plan'].sudo().browse(plan_id)
        max_users = int(plan.max_users)
        total_storage_limit = int(plan.total_storage_limit)
        if order_id and client and plan.topup_ids:
            order = request.env['sale.order'].sudo().browse(int(order_id))
            params_list = []
            users, storage, additional_invoice_lines = self.get_topup_info(order, plan, client)
            if users != max_users:
                params_list.append({'key': 'saas_client.max_users', 'value': users})
            if storage != total_storage_limit:
                params_list.append({'key': 'saas_client.total_storage_limit', 'value': storage})

            if params_list:
                client.upgrade(payload={'params': params_list})
                # request.env['saas_portal.client_topup'].sudo().create({
                #     'client_id': client.id,
                #     'topup_users': users if users != max_users else None,
                #     'topup_storage': storage if storage != total_storage_limit else None,
                # })

            if client.contract_id and additional_invoice_lines:
                #client.contract_id.recurring_invoice_line_ids = additional_invoice_lines
                for invoice_line in additional_invoice_lines:
                    request.env['account.analytic.invoice.line'].sudo().create(invoice_line)

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

        instances = False
        plan = False
        if order:
            base_plan_product = order.order_line.mapped('product_id').filtered(lambda product: product.saas_plan_id != False and product.saas_product_type == 'base')
            if not base_plan_product:
                partner = request.env.user.partner_id
                SaasPortalClient = request.env['saas_portal.client']
                instances = SaasPortalClient.sudo().search([('partner_id.id', '=', partner.id)])
            elif base_plan_product.saas_plan_id:
                users, storage, additional_invoice_lines = self.get_topup_info(order, base_plan_product.saas_plan_id, None)
                #additional_users = base_plan_product.saas_plan_id.max_users - users
                #additional_storage = base_plan_product.saas_plan_id.total_storage_limit - storage
                plan = {
                    #'plan_users': base_plan_product.saas_plan_id.max_users,
                    #'additional_users': additional_users,
                    'max_allowed_users': users,
                    #'plan_storage': base_plan_product.saas_plan_id.total_storage_limit,
                    #'additional_storage': additional_storage,
                    'max_allowed_storage': storage,
                }

        values = {
            'website_sale_order': order,
            'post': post,
            'base_saas_domain': base_saas_domain,
            'escape': lambda x: x.replace("'", r"\'"),
            'partner': order.partner_id.id,
            'order': order,
            'instances': instances,
            'plan': plan
        }

        return request.render("website_sale.extra_info", values)

    @http.route(['/shop/checkout'], type='http', auth="public", website=True)
    def checkout(self, **post):
        order = request.website.sale_get_order()

        if order and order.order_line.mapped('product_id').filtered(lambda product: product.saas_plan_id != False and product.saas_product_type == 'base'):
            lines = order.order_line.filtered(lambda line: line.product_id.saas_plan_id != False and line.product_id.saas_product_type == 'base')
            for line in lines:
                if line.product_uom_qty > 1:
                    return request.redirect('/shop/cart/')

        redirection = self.checkout_redirection(order)
        if redirection:
            return redirection

        if order.partner_id.id == request.website.user_id.sudo().partner_id.id:
            return request.redirect('/shop/address')

        for f in self._get_mandatory_billing_fields():
            if not order.partner_id[f]:
                return request.redirect('/shop/address?partner_id=%d' % order.partner_id.id)

        values = self.checkout_values(**post)

        values.update({'website_sale_order': order})

        # Avoid useless rendering if called in ajax
        if post.get('xhr'):
            return 'ok'
        return request.render("website_sale.checkout", values)

    @http.route(['/shop/cart'], type='http', auth="public", website=True)
    def cart(self, access_token=None, revive='', **post):
        """
        Main cart management + abandoned cart revival
        access_token: Abandoned cart SO access token
        revive: Revival method when abandoned cart. Can be 'merge' or 'squash'
        """
        order = request.website.sale_get_order()
        if order and order.state != 'draft':
            request.session['sale_order_id'] = None
            order = request.website.sale_get_order()
        values = {}
        if access_token:
            abandoned_order = request.env['sale.order'].sudo().search([('access_token', '=', access_token)], limit=1)
            if not abandoned_order:  # wrong token (or SO has been deleted)
                return request.render('website.404')
            if abandoned_order.state != 'draft':  # abandoned cart already finished
                values.update({'abandoned_proceed': True})
            elif revive == 'squash' or (revive == 'merge' and not request.session[
                'sale_order_id']):  # restore old cart or merge with unexistant
                request.session['sale_order_id'] = abandoned_order.id
                return request.redirect('/shop/cart')
            elif revive == 'merge':
                abandoned_order.order_line.write({'order_id': request.session['sale_order_id']})
                abandoned_order.action_cancel()
            elif abandoned_order.id != request.session[
                'sale_order_id']:  # abandoned cart found, user have to choose what to do
                values.update({'access_token': abandoned_order.access_token})

        if order:
            from_currency = order.company_id.currency_id
            to_currency = order.pricelist_id.currency_id
            compute_currency = lambda price: from_currency.compute(price, to_currency)
        else:
            compute_currency = lambda price: price

        valid = True
        if order and order.order_line.mapped('product_id').filtered(lambda product: product.saas_plan_id != False and product.saas_product_type == 'base'):
            lines = order.order_line.filtered(lambda line: line.product_id.saas_plan_id != False and line.product_id.saas_product_type == 'base')
            for line in lines:
                if line.product_uom_qty > 1:
                    valid = False

        values.update({
            'website_sale_order': order,
            'compute_currency': compute_currency,
            'suggested_products': [],
            'valid': valid,
        })
        if order:
            _order = order
            if not request.env.context.get('pricelist'):
                _order = order.with_context(pricelist=order.pricelist_id.id)
            values['suggested_products'] = _order._cart_accessories()

        if post.get('type') == 'popover':
            # force no-cache so IE11 doesn't cache this XHR
            return request.render("website_sale.cart_popover", values, headers={'Cache-Control': 'no-cache'})

        return request.render("website_sale.cart", values)

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
        if order:
            if order.order_line.mapped('product_id').filtered(lambda product: product.saas_plan_id != False):
                plan_id = order.order_line.mapped('product_id').filtered(lambda product: product.saas_plan_id != False)[:1].saas_plan_id.id
                dbname = order.saas_dbname
                client = order.saas_instance_id # request.env['saas_portal.client'].sudo().search([('name', '=', dbname)], limit=1)
                if plan_id and dbname and not client:
                    redirect = '/saas_portal/add_new_client'
                    redirect_url = '%s?dbname=%s&plan_id=%s&order_id=%s' % (
                        redirect, dbname, plan_id, order.id
                    )
                    return request.redirect(redirect_url)
                if plan_id and client:
                    self.upgrade_client_with_topup(client, plan_id, order.id)

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
        if 'instance_id' in kwargs:
            order.write({'saas_instance_id': kwargs['instance_id']})

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
