from odoo import fields, models
from odoo.exceptions import UserError


class AuditLogLine(models.Model):
    _name = 'audit.log.line'
    _description = "Détail d'un champ modifié"
    _order = 'id'


    log_id = fields.Many2one('audit.log', string="Journal", required=True, ondelete='cascade', index=True)

    # technical name + readable label of the field, kept as text so they survive if the field is removed
    field_name = fields.Char(string="Champ (technique)", readonly=True)
    field_label = fields.Char(string="Champ", readonly=True)

    # values are always stored as text, whatever the type of the field was
    old_value = fields.Text(string="Ancienne valeur", readonly=True)
    new_value = fields.Text(string="Nouvelle valeur", readonly=True)

    # same protection as audit.log, lines are read only
    def write(self, vals):
        raise UserError("Les lignes de journal ne peuvent pas être modifiées.")

    def unlink(self):
        raise UserError("Les lignes de journal ne peuvent pas être supprimées.")
