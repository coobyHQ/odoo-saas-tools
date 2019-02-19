import requests
import random
import string
from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class SaasPortalClientCreateClient(models.TransientModel):
    _name = 'saas_portal.client_create_client'

    subdomain = fields.Char('New Subdomain', required=False)
    plan_id = fields.Many2one('saas_portal.plan', string='Plan', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Partner')
    user_id = fields.Many2one('res.users', string='User')
    notify_user = fields.Boolean(help='Notify user by email when database will have been created',
                                 default=True)
    async_creation = fields.Boolean(
        'Asynchronous',
        default=False, help='Asynchronous creation of client base')
    trial = fields.Boolean('Trial')

    @api.onchange('user_id')
    def update_partner(self):
        if self.user_id:
            self.partner_id = self.user_id.partner_id

    @api.multi
    def apply(self):
        self.ensure_one()
        plan_id = self.plan_id
        res = plan_id.create_new_database(
            dbname=self.name,
            partner_id=self.partner_id.id,
            user_id=self.user_id.id,
            notify_user=self.notify_user,
            # moved   support_team_id=self.support_team_id.id,
            async=self.async_creation,
            trial=self.trial)
        if self.async_creation:
            return
        client = self.env['saas_portal.client'].browse(res.get('id'))
        client.server_id.action_sync_server()
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'saas_portal.client',
            'res_id': client.id,
            'target': 'current',
        }

"""
class SaasPortalDuplicateClient(models.TransientModel):
    _name = 'saas_portal.duplicate_client'

    def _default_client_id(self):
        return self._context.get('active_id')

    def _default_partner(self):
        client_id = self._default_client_id()
        if client_id:
            client = self.env['saas_portal.client'].browse(client_id)
            return client.partner_id
        return ''

    def _default_expiration(self):
        client_id = self._default_client_id()
        if client_id:
            client = self.env['saas_portal.client'].browse(client_id)
            return client.plan_id.expiration
        return ''

    name = fields.Char('Database Name', required=True)
    client_id = fields.Many2one(
        'saas_portal.client', string='Base Client',
        readonly=True, default=_default_client_id)
    expiration = fields.Integer('Expiration', default=_default_expiration)
    partner_id = fields.Many2one(
        'res.partner', string='Partner', default=_default_partner)

    @api.multi
    def apply(self):
        self.ensure_one()
        res = self.client_id.duplicate_database(
            dbname=self.name, partner_id=self.partner_id.id, expiration=None)
        client = self.env['saas_portal.client'].browse(res.get('id'))
        client.server_id.action_sync_server()
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'saas_portal.client',
            'res_id': client.id,
            'target': 'current',
        }

class SaasPortalRenameDatabase(models.TransientModel):
    _name = 'saas_portal.rename_database'

    def _default_client_id(self):
        return self._context.get('active_id')
    # Todo domain field
    domain = fields.Char(related='client_id.domain', string='Domain', readonly=True)
    subdomain = fields.Char('New Subdomain', required=True)
    client_id = fields.Many2one('saas_portal.client', string='Base Client',
                                readonly=True, default=_default_client_id)

    @api.multi
    def apply(self):
        self.ensure_one()
        self.client_id.rename_subdomain(new_subdomain=self.subdomain)
        return {
            'type': 'ir.actions.act_window_close',
        }
"""

