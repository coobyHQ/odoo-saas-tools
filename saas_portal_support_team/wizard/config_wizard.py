from odoo import api, fields, models


class SaasPortalCreateClient(models.TransientModel):
    _name = 'saas_portal.create_client_inherit_support'
    _inherit = 'saas_portal.create_client'

    support_team_id = fields.Many2one(
        'saas_portal.support_team', 'Support Team',
        default=lambda self: self.env.user.support_team_id)
    """
    @api.multi
    def apply(self):
        self.ensure_one()
        plan_id = self.plan_id
        res = plan_id.create_new_database(
            dbname=self.name,
            partner_id=self.partner_id.id,
            user_id=self.user_id.id,
            notify_user=self.notify_user,
            support_team_id=self.support_team_id.id,
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
