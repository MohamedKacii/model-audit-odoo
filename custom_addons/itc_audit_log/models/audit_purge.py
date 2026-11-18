from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

ADMIN_GROUP = 'itc_audit_log.group_audit_admin'


class AuditPurge(models.Model):
    # one record per purge, it proves that entries were deleted, by whom and up to when
    _name = 'audit.purge'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Trace d'une purge du journal"
    _order = 'date desc, id desc'
    _mail_post_access = 'read'

    name = fields.Char(string="Purge", required=True, readonly=True)
    date = fields.Datetime(string="Date de la purge", required=True, default=fields.Datetime.now, readonly=True)
    user_id = fields.Many2one('res.users', string="Effectuée par", ondelete='set null', readonly=True)
    cutoff = fields.Datetime(string="Entrées antérieures au", required=True, readonly=True)
    entries_count = fields.Integer(string="Entrées supprimées", readonly=True)

    # a trace can never be edited or deleted, otherwise a purge could hide itself (only odoo's own mail field gets through)
    def write(self, vals):
        if set(vals) <= {'message_main_attachment_id'}:
            return super().write(vals)
        raise UserError("Les traces de purge ne peuvent pas être modifiées.")

    def unlink(self):
        raise UserError("Les traces de purge ne peuvent pas être supprimées.")


class AuditPurgeWizard(models.TransientModel):
    _name = 'audit.purge.wizard'
    _description = "Assistant de purge du journal"

    cutoff = fields.Datetime(
        string="Supprimer les entrées antérieures au", required=True,
        default=lambda self: fields.Datetime.now() - timedelta(days=90))
    entries_count = fields.Integer(string="Entrées concernées", compute='_compute_entries_count')

    @api.depends('cutoff')
    def _compute_entries_count(self):
        for wizard in self:
            wizard.entries_count = self.env['audit.log'].search_count(
                [('date', '<', wizard.cutoff)]) if wizard.cutoff else 0

    def action_purge(self):
        self.ensure_one()
        # the menu and the button are hidden for other users, but the rule itself is checked here on the server
        if not self.env.user.has_group(ADMIN_GROUP):
            raise AccessError("Seuls les administrateurs de la traçabilité peuvent purger le journal.")
        if self.cutoff > fields.Datetime.now():
            raise UserError("La date limite ne peut pas être dans le futur.")
        deleted = self.env['audit.log']._purge_before(self.cutoff)
        purge = self.env['audit.purge'].sudo().create({
            'name': "Purge jusqu'au %s" % fields.Datetime.to_string(self.cutoff),
            'user_id': self.env.uid,
            'cutoff': self.cutoff,
            'entries_count': deleted,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'audit.purge',
            'res_id': purge.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
        }
