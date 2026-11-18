from odoo import fields, models
from odoo.exceptions import AccessError, UserError


class AuditLog(models.Model):
    _name = 'audit.log'
    # chatter on the entry, so people can leave notes on it even though the entry itself is read only
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Journal des opérations"
    _order = 'date desc, id desc'
    _rec_name = 'record_name'
    # reading an entry is enough to post a note on it (normally odoo asks for write access)
    _mail_post_access = 'read'

    date = fields.Datetime(string="Date", required=True, default=fields.Datetime.now, readonly=True)

    user_id = fields.Many2one('res.users', string="Utilisateur", ondelete='set null', readonly=True)
    model_name = fields.Char(string="Modèle (technique)", index=True, readonly=True)
    model_label = fields.Char(string="Modèle", readonly=True)

    res_id = fields.Integer(string="ID de l'enregistrement", readonly=True)
    record_name = fields.Char(string="Enregistrement", readonly=True)

    operation = fields.Selection([
        ('create', "Création"),
        ('write', "Modification"),
        ('unlink', "Suppression"),
        ('archive', "Archivage"),
        ('unarchive', "Désarchivage"),
    ], string="Opération", required=True, index=True, readonly=True)


    # one line per changed field
    line_ids = fields.One2many('audit.log.line', 'log_id', string="Détails", readonly=True)

    # logs are read only, nobody edits or deletes them (section 6 of the spec)
    #(im actually overriding write and unlink here which are defined in odoo models without calling (super))
    # one exception: odoo itself sets this technical field on the record when an attachment is posted in the chatter
    def write(self, vals):
        if set(vals) <= {'message_main_attachment_id'}:
            return super().write(vals)
        raise UserError("Les journaux ne peuvent pas être modifiés.")

    def unlink(self):
        raise UserError("Les journaux ne peuvent pas être supprimés.")

    # the ONLY way to delete entries (see ADR 0001), plain sql on purpose so the immutability above stays untouched
    # it starts with an underscore so it cannot be called from the browser, only from the purge wizard
    def _purge_before(self, cutoff):
        if not self.env.user.has_group('itc_audit_log.group_audit_admin'):
            raise AccessError("Seuls les administrateurs de la traçabilité peuvent purger le journal.")
        cr = self.env.cr
        self.flush_model()
        old_entries = "SELECT id FROM audit_log WHERE date < %s"
        # the chatter rows that hang on the entries go first, then the entries (their details follow by cascade)
        cr.execute("DELETE FROM mail_message WHERE model = 'audit.log' AND res_id IN (%s)" % old_entries, (cutoff,))
        cr.execute("DELETE FROM mail_followers WHERE res_model = 'audit.log' AND res_id IN (%s)" % old_entries, (cutoff,))
        cr.execute("DELETE FROM mail_activity WHERE res_model = 'audit.log' AND res_id IN (%s)" % old_entries, (cutoff,))
        cr.execute("DELETE FROM audit_log WHERE date < %s", (cutoff,))
        deleted = cr.rowcount
        self.env.invalidate_all()
        return deleted
