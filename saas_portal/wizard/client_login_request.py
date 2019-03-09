import requests
import random
import string
from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class SaasPortalEditDatabase(models.TransientModel):
    """
    Model to get access to a client instance via a permission link
    """
    _name = 'saas_portal.edit_database'

    name = fields.Char(readonly=True)
    active_id = fields.Char()
    active_model = fields.Char()
    edit_database_url = fields.Char(readonly=True)
    login_allowed = fields.Boolean('Login Request Allowed', default=False)
    client_email = fields.Char(readonly=True)

    @api.model
    def default_get(self, fields):
        res = super(SaasPortalEditDatabase, self).default_get(fields)
        res['active_model'] = self._context.get('active_model')
        res['active_id'] = self._context.get('active_id')

        login_allowed = False
        active_record = self.env[res['active_model']].browse(int(res['active_id']))
        if res['active_model'] == 'saas_portal.client':
            if active_record.login_allowed:
                login_allowed = True
            res['client_email'] = active_record and active_record.partner_id and active_record.partner_id.email
        elif res['active_model'] == 'saas_portal.database':
            login_allowed = True
        else:
            active_record = active_record.template_id
            login_allowed = True
        res['name'] = active_record.name
        res['edit_database_url'] = active_record._request_url('/saas_server/edit_database')
        res['login_allowed'] = login_allowed
        return res

    @api.multi
    def login_to_instance(self):
        if not self.edit_database_url:
            raise ValidationError(_("No URL to login to!"))

        if self.active_model == 'saas_portal.client':
            instance = self.env[self.active_model].browse(int(self.active_id))
            instance.login_allowed = False

        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'name': 'Login redirection',
            'url': self.edit_database_url
        }

    @api.multi
    def request_permission(self):
        if not self.client_email:
            raise ValidationError(_("A client does not have an e-mail address, please add it!"))

        instance = self.env[self.active_model].browse(int(self.active_id))
        instance.login_permission_token = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))

        template = None
        ir_config_param = self.env['ir.config_parameter'].sudo()
        login_permission_email_template = self.env.ref('saas_portal.login_permission_email_template', raise_if_not_found=False)
        if login_permission_email_template:
            # send an email
            login_permission_email_template.with_context(tracking_disable=True, mail_create_nolog=True, mail_auto_delete=True).send_mail(instance.id, force_send=True)

            # add a message to chatter
            change_comment = ('<b>Login request sent by staff </b>' +
                              '<ul class=\"o_mail_thread_message_tracking\">\n'
                              '<li>Login request sent by staff to ' + self.client_email + '.</li>'
                                                                                          '</ul>')
            instance.message_post(body=change_comment, subject="Client instance changed by staff",
                                  subtype='mail.mt_comment', message_type='comment')
        else:
            raise ValidationError(("No email template found for requesting login permission from the client!"))
