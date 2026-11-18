from odoo import api, fields, models
from odoo.tools.misc import human_size

# the properties of a field that we compare, the key is the name on the snapshot row
COMPARED = {
    'label': "Libellé",
    'ttype': "Type",
    'required': "Obligatoire",
    'readonly': "Lecture seule",
    'stored': "Stocké en base",
    'relation': "Modèle lié",
    'selection': "Options de sélection",
}

KINDS = [
    ('entity_added', "Entité ajoutée à l'audit"),
    ('entity_removed', "Entité retirée de l'audit"),
    ('model_deleted', "Modèle supprimé d'Odoo"),
    ('field_added', "Champ ajouté"),
    ('field_removed', "Champ supprimé"),
    ('field_changed', "Champ modifié"),
]


def _text(value):
    # one way to write any value, so True/False/empty compare and display the same everywhere
    if value is False or value is None:
        return ''
    return str(value)


class AuditSnapshot(models.Model):
    _name = 'audit.snapshot'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Instance du schéma des entités auditées"
    _order = 'date desc, id desc'

    name = fields.Char(
        string="Nom", required=True, tracking=True,
        default=lambda self: "Instance du %s" % fields.Datetime.now().strftime('%d/%m/%Y %H:%M'))
    date = fields.Datetime(string="Date", required=True, default=fields.Datetime.now, readonly=True)
    user_id = fields.Many2one('res.users', string="Prise par", default=lambda self: self.env.user, readonly=True)
    entity_ids = fields.One2many('audit.snapshot.entity', 'snapshot_id', string="Entités", readonly=True)
    field_ids = fields.One2many('audit.snapshot.field', 'snapshot_id', string="Champs", readonly=True)
    entity_count = fields.Integer(string="Nombre d'entités", compute='_compute_counts')
    field_count = fields.Integer(string="Nombre de champs", compute='_compute_counts')
    # how much room this snapshot takes in the database
    storage_bytes = fields.Integer(string="Taille (octets)", compute='_compute_storage')
    storage_size = fields.Char(string="Place occupée", compute='_compute_storage')

    @api.depends('entity_ids', 'field_ids')
    def _compute_counts(self):
        for snapshot in self:
            snapshot.entity_count = len(snapshot.entity_ids)
            snapshot.field_count = len(snapshot.field_ids)

    @api.depends('entity_ids', 'field_ids')



    # pg_column_size gives the size in bytes of each stored row, we add up the rows of each snapshot
    def _compute_storage(self):
        sizes = {}
        if self.ids:
            self.env['audit.snapshot.entity'].flush_model()
            self.env['audit.snapshot.field'].flush_model()
            self.env.cr.execute("""
                SELECT snapshot_id, SUM(row_size) FROM (
                    SELECT snapshot_id, pg_column_size(e.*) AS row_size
                      FROM audit_snapshot_entity e WHERE snapshot_id IN %(ids)s
                    UNION ALL
                    SELECT snapshot_id, pg_column_size(f.*)
                      FROM audit_snapshot_field f WHERE snapshot_id IN %(ids)s
                ) rows GROUP BY snapshot_id
            """, {'ids': tuple(self.ids)})
            sizes = dict(self.env.cr.fetchall())
        for snapshot in self:
            size = int(sizes.get(snapshot.id, 0))
            snapshot.storage_bytes = size
            snapshot.storage_size = human_size(size) or "0 bytes"

    # what the structure of the audited entities looks like right now: {model: {'label': ..., 'fields': {name: {...}}}}
    @api.model
    def _current_schema(self):
        # sudo because only system administrators may read ir.model.fields, the audit administrators may not
        # the entities that are really audited: configurations in the state "En cours"
        configs = self.env['audit.model.config'].sudo().search([('state', '=', 'running')])
        schema = {}
        for model in configs.model_id:
            # labels are read in english so two users with different languages never see a false difference
            fields_in_db = self.env['ir.model.fields'].sudo().with_context(lang='en_US').search([('model_id', '=', model.id)])
            schema[model.model] = {
                'label': model.name,
                'fields': {
                    field.name: {
                        'label': _text(field.field_description),
                        'ttype': _text(field.ttype),
                        'required': _text(field.required),
                        'readonly': _text(field.readonly),
                        'stored': _text(field.store),
                        'relation': _text(field.relation),
                        'selection': ';'.join(
                            '%s=%s' % (option.value, option.name)
                            for option in field.selection_ids.sorted('sequence')),
                    } for field in fields_in_db
                },
            }
        return schema

    def _stored_schema(self):
        self.ensure_one()
        schema = {entity.model_name: {'label': entity.model_label, 'fields': {}} for entity in self.entity_ids}
        for field in self.field_ids:
            schema.setdefault(field.model_name, {'label': field.model_name, 'fields': {}})['fields'][field.field_name] = {
                name: _text(field[name]) for name in COMPARED
            }
        return schema

    # the differences between this snapshot and the structure right now, as a list of dictionaries
    def _compute_diff(self):
        self.ensure_one()
        old, new = self._stored_schema(), self._current_schema()
        rows = []

        def row(kind, model_name, label, field_name='', attribute='', old_value='', new_value=''):
            rows.append({
                'kind': kind, 'model_name': model_name, 'model_label': label, 'field_name': field_name,
                'attribute': attribute, 'old_value': old_value, 'new_value': new_value,
            })

        for model_name in sorted(set(old) | set(new)):
            if model_name not in old:
                row('entity_added', model_name, new[model_name]['label'])
                continue
            if model_name not in new:
                kind = 'entity_removed' if model_name in self.env.registry else 'model_deleted'
                row(kind, model_name, old[model_name]['label'])
                continue
            label = new[model_name]['label']
            old_fields, new_fields = old[model_name]['fields'], new[model_name]['fields']
            for field_name in sorted(set(old_fields) | set(new_fields)):
                if field_name not in old_fields:
                    row('field_added', model_name, label, field_name, '', '', new_fields[field_name]['ttype'])
                elif field_name not in new_fields:
                    row('field_removed', model_name, label, field_name, '', old_fields[field_name]['ttype'], '')
                else:
                    for attribute, title in COMPARED.items():
                        before, after = old_fields[field_name][attribute], new_fields[field_name][attribute]
                        if before != after:
                            row('field_changed', model_name, label, field_name, title, before, after)
        return rows

    @api.model_create_multi
    def create(self, vals_list):
        snapshots = super().create(vals_list)
        for snapshot in snapshots:
            snapshot._capture()
        return snapshots


    # the picture is taken when the snapshot is saved
    def _capture(self):
        self.ensure_one()
        entities, fields_rows = [], []
        for model_name, entity in self._current_schema().items():
            entities.append({'snapshot_id': self.id, 'model_name': model_name, 'model_label': entity['label']})
            for field_name, attrs in entity['fields'].items():
                fields_rows.append({'snapshot_id': self.id, 'model_name': model_name, 'field_name': field_name, **attrs})
        self.env['audit.snapshot.entity'].create(entities)
        self.env['audit.snapshot.field'].create(fields_rows)

    def action_compare(self):
        self.ensure_one()
        Diff = self.env['audit.snapshot.diff']
        # one comparison at a time per user and snapshot, a new click replaces the previous result
        Diff.search([('snapshot_id', '=', self.id), ('create_uid', '=', self.env.uid)]).unlink()
        Diff.create([dict(row, snapshot_id=self.id) for row in self._compute_diff()])
        return {
            'type': 'ir.actions.act_window',
            'name': "Comparaison avec « %s »" % self.name,
            'res_model': 'audit.snapshot.diff',
            'view_mode': 'tree',
            'views': [(False, 'tree')],
            'domain': [('snapshot_id', '=', self.id), ('create_uid', '=', self.env.uid)],
            'context': {'create': False, 'edit': False, 'delete': False},
            'help': "<p class='o_view_nocontent_smiling_face'>Aucune différence</p>"
                    "<p>La structure actuelle est identique à cette instance.</p>",
        }


class AuditSnapshotEntity(models.Model):
    _name = 'audit.snapshot.entity'
    _description = "Entité d'une instance"
    _order = 'model_name'

    snapshot_id = fields.Many2one('audit.snapshot', required=True, ondelete='cascade', index=True)
    model_name = fields.Char(string="Modèle (technique)", readonly=True)
    model_label = fields.Char(string="Entité", readonly=True)


class AuditSnapshotField(models.Model):
    _name = 'audit.snapshot.field'
    _description = "Champ d'une instance"
    _order = 'model_name, field_name'

    snapshot_id = fields.Many2one('audit.snapshot', required=True, ondelete='cascade', index=True)
    model_name = fields.Char(string="Modèle (technique)", readonly=True)
    field_name = fields.Char(string="Champ (technique)", readonly=True)
    label = fields.Char(string="Libellé", readonly=True)
    ttype = fields.Char(string="Type", readonly=True)
    required = fields.Char(string="Obligatoire", readonly=True)
    readonly = fields.Char(string="Lecture seule", readonly=True)
    stored = fields.Char(string="Stocké en base", readonly=True)
    relation = fields.Char(string="Modèle lié", readonly=True)
    selection = fields.Text(string="Options de sélection", readonly=True)


# the result of a comparison, it only lives for a short time (transient) and is rebuilt at each click
class AuditSnapshotDiff(models.TransientModel):
    _name = 'audit.snapshot.diff'
    _description = "Différence entre une instance et l'état actuel"
    _order = 'model_name, field_name, id'

    snapshot_id = fields.Many2one('audit.snapshot', required=True, ondelete='cascade')
    kind = fields.Selection(KINDS, string="Type de différence", required=True)
    model_name = fields.Char(string="Modèle (technique)")
    model_label = fields.Char(string="Entité")
    field_name = fields.Char(string="Champ")
    attribute = fields.Char(string="Propriété")
    old_value = fields.Char(string="Avant")
    new_value = fields.Char(string="Maintenant")
