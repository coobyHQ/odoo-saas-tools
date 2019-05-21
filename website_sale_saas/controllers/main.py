from odoo.http import request
from odoo import http, fields, SUPERUSER_ID, _
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.website_sale.controllers.main import WebsiteSaleForm
from odoo.addons.saas_portal.controllers.main import SaasPortal
from odoo.exceptions import ValidationError
from odoo.addons.base.models.ir_qweb_fields import nl2br
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

        dbname = post.get('dbname') #self.get_full_dbname(post.get('dbname'), int(post.get('plan_id', 0) or 0))
        user_id = request.session.uid
        partner_id = None
        if user_id:
            user = request.env['res.users'].browse(user_id)
            partner_id = user.partner_id.id
        plan = self.get_plan(int(post.get('plan_id', 0) or 0))
        trial = bool(post.get('trial', False))
        order_id = post.get('order_id')
        lang=None
        template_db = None
        if order_id:
            order = request.env['sale.order'].sudo().browse(int(order_id))
            base_plan_product = order.order_line.mapped('product_id').filtered(
                lambda product: product.saas_plan_id != False and product.saas_product_type == 'base')
            if base_plan_product.attribute_value_ids:
                for attr in base_plan_product.attribute_value_ids:
                    if attr.attribute_id and attr.attribute_id.saas_code == 'lang':
                        if attr.saas_lang:
                            lang = attr.saas_lang
                            if attr.template_ids:
                                for templ in attr.template_ids:
                                    if base_plan_product.saas_plan_id.id in templ.plan_ids.ids:
                                        template_db = templ.name
                                        break
        else:
            if post.get('trial_product_id', False):
                trial_product = request.env['product.product'].sudo().browse(int(post.get('trial_product_id')))
                for attr in trial_product.attribute_value_ids:
                    if attr.attribute_id and attr.attribute_id.saas_code == 'lang':
                        if attr.saas_lang:
                            lang = attr.saas_lang
                            if attr.template_ids:
                                for templ in attr.template_ids:
                                    if base_plan_product.saas_plan_id.id in templ.plan_ids.ids:
                                        template_db = templ.name
                                        break
        try:
            res = plan.create_new_database(dbname=dbname,
                                           user_id=user_id,
                                           partner_id=partner_id,
                                           trial=trial,
                                           order_id=order_id,
                                           lang=lang,
                                           template_db=template_db)
        except MaximumDBException:
            _logger.info("MaximumDBException")
            url = request.env['ir.config_parameter'].sudo().get_param('saas_portal.page_for_maximumdb', '/')
            return werkzeug.utils.redirect(url)
        except MaximumTrialDBException:
            _logger.info("MaximumTrialDBException")
            url = request.env['ir.config_parameter'].sudo().get_param('saas_portal.page_for_maximumtrialdb', '/')
            return werkzeug.utils.redirect(url)


        if plan and plan.on_create == 'login':
            return werkzeug.utils.redirect(res.get('url'))
        elif order_id:
            return request.redirect('/shop/confirmation')


class SaasCreateInstanceAfterValidating(WebsiteSale):

    def get_saas_domain(self, order, base_plan_product):
        config = request.env['ir.config_parameter']
        full_param = 'saas_portal.base_saas_domain'
        base_saas_domain = config.sudo().get_param(full_param)
        if order:
            if base_plan_product and base_plan_product.saas_plan_id and base_plan_product.saas_plan_id.domain:
                base_saas_domain = base_plan_product.saas_plan_id.domain
            if base_plan_product.attribute_value_ids:
                for attr in base_plan_product.attribute_value_ids:
                    if attr.attribute_id and attr.attribute_id.saas_code == 'lang':
                        if attr.saas_lang:
                            lang = attr.saas_lang
                            if attr.template_ids:
                                for templ in attr.template_ids:
                                    if base_plan_product.saas_plan_id.id in templ.plan_ids.ids:
                                        base_saas_domain = templ.domain
                                        break
        return base_saas_domain

    def upgrade_client_with_topup(self, client, plan_id, order_id):
        plan = request.env['saas_portal.plan'].sudo().browse(plan_id)
        if order_id and client:
            if not plan: plan = client.plan_id
            max_users = int(client.max_users)
            total_storage_limit = int(client.total_storage_limit)
            order = request.env['sale.order'].sudo().browse(int(order_id))
            client_vals = {}
            users, storage, additional_invoice_lines = plan.get_topup_info(order, client)
            if users != max_users:
                client_vals.update(max_users=str(users))
            if storage != total_storage_limit:
                client_vals.update(total_storage_limit=storage)
            if client_vals:
                client.write(client_vals)

            if client.contract_id and additional_invoice_lines:
                for invoice_line in additional_invoice_lines:
                    request.env['account.analytic.invoice.line'].sudo().create(invoice_line)

    # ------------------------------------------------------
    # Extra step to add dbname
    # ------------------------------------------------------
    @http.route(['/shop/extra_info'], type='http', auth="public", website=True)
    def extra_info(self, **post):
        # Check that this option is activated
        extra_step = request.website.viewref('website_sale.extra_info_option')
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

        # added, start
        base_saas_domain = None
        dbname = None
        if not post.get('dbname', False):
            if order and order.saas_dbname:
                dbname = order.saas_dbname
                post['dbname'] = dbname

        instances = False
        plan = False
        if order:
            base_plan_product = order.order_line.mapped('product_id').filtered(lambda product: product.saas_plan_id != False and product.saas_product_type == 'base')
            if not base_plan_product:
                partner = request.env.user.partner_id
                SaasPortalClient = request.env['saas_portal.client']
                instances = SaasPortalClient.sudo().search([('partner_id.id', '=', partner.id)])
            elif base_plan_product.saas_plan_id:
                if not post.get('base_saas_domain', False):
                    base_saas_domain = self.get_saas_domain(order, base_plan_product)
                    post['base_saas_domain'] = base_saas_domain

                users, storage, additional_invoice_lines = base_plan_product.saas_plan_id.get_topup_info(order, None)
                additional_users = users - base_plan_product.saas_plan_id.max_users
                additional_storage = storage - base_plan_product.saas_plan_id.max_storage
                plan = {
                    'plan_users': base_plan_product.saas_plan_id.max_users,
                    'additional_users': additional_users,
                    'max_allowed_users': users,
                    'plan_storage': base_plan_product.saas_plan_id.max_storage,
                    'additional_storage': additional_storage,
                    'max_allowed_storage': storage,
                }
        # added, end

        values = {
            'website_sale_order': order,
            'post': post,
            'base_saas_domain': base_saas_domain,
            'dbname': dbname,
            'dbname_base_saas_domain': base_saas_domain,
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

        # added, start
        if order and order.order_line.mapped('product_id').filtered(lambda product: product.saas_plan_id != False and product.saas_product_type == 'base'):
            lines = order.order_line.filtered(lambda line: line.product_id.saas_plan_id != False and line.product_id.saas_product_type == 'base')
            for line in lines:
                if line.product_uom_qty > 1:
                    return request.redirect('/shop/cart/')
        # added, end

        redirection = self.checkout_redirection(order)
        if redirection:
            return redirection

        if order.partner_id.id == request.website.user_id.sudo().partner_id.id:
            return request.redirect('/shop/address')

        for f in self._get_mandatory_billing_fields():
            if not order.partner_id[f]:
                return request.redirect('/shop/address?partner_id=%d' % order.partner_id.id)

        values = self.checkout_values(**post)

        if post.get('express'):
            return request.redirect('/shop/confirm_order')

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
            elif revive == 'squash' or (revive == 'merge' and not request.session['sale_order_id']):  # restore old cart or merge with unexistant
                request.session['sale_order_id'] = abandoned_order.id
                return request.redirect('/shop/cart')
            elif revive == 'merge':
                abandoned_order.order_line.write({'order_id': request.session['sale_order_id']})
                abandoned_order.action_cancel()
            elif abandoned_order.id != request.session['sale_order_id']:  # abandoned cart found, user have to choose what to do
                values.update({'access_token': abandoned_order.access_token})

        if order:
            from_currency = order.company_id.currency_id
            to_currency = order.pricelist_id.currency_id
            compute_currency = lambda price: from_currency._convert(price, to_currency, request.env.user.company_id, fields.Date.today())
        else:
            compute_currency = lambda price: price

        # added, start
        valid = True
        if order and order.order_line.mapped('product_id').filtered(lambda product: product.saas_plan_id != False and product.saas_product_type == 'base'):
            lines = order.order_line.filtered(lambda line: line.product_id.saas_plan_id != False and line.product_id.saas_product_type == 'base')
            if len(lines) > 1: valid = False
            for line in lines:
                if line.product_uom_qty > 1:
                    valid = False
        # added, end

        values.update({
            'website_sale_order': order,
            'compute_currency': compute_currency,
            'date': fields.Date.today(),
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
                    redirect_url = '%s?dbname=%s&plan_id=%s&order_id=%s' % (redirect, dbname, plan_id, order.id)
                    return request.redirect(redirect_url)
                elif client:
                    self.upgrade_client_with_topup(client, plan_id, order.id)

        return request.redirect('/shop/confirmation')

    @http.route(['/shop/payment'], type='http', auth="public", website=True)
    def payment(self, **post):
        order = request.website.sale_get_order()
        if order:
            dbname = order.saas_dbname
            if dbname and dbname == 'ERROR_DB_EXISTS!': #TODO improve
                if request.website:
                    msg = _('Please choose another web address name.')
                    msg_title = 'This Odoo instance name already exists!'
                    http.request.website.add_status_message(msg, type_='info', title=msg_title)
                extra_step = request.env.ref('website_sale.extra_info_option')
                if extra_step.active:
                    return request.redirect("/shop/extra_info")

        return super(SaasCreateInstanceAfterValidating, self).payment(**post)


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

        if 'dbname' in kwargs and 'dbname_base_saas_domain' in kwargs:
            dbname = (kwargs['dbname'] or '') + '.' + (kwargs['dbname_base_saas_domain'] or '')
            if request.env['saas_portal.database'].sudo().search([('name', '=', dbname)]):
                order.write({'saas_dbname': 'ERROR_DB_EXISTS!'}) #TODO improve
            else:
                order.write({'saas_dbname': kwargs['dbname']})
                if request.website:
                    msg = _('Please wait a few seconds for it to complete.')
                    msg_title = 'Your Instance will be created upon confirming the order!'
                    http.request.website.add_status_message(msg, type_='info', title=msg_title)
                    # return http.request.render('website_sale_saas.add_saas_instance_notification')
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
