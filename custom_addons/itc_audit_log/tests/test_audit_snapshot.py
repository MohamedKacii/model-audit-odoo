from odoo.exceptions import AccessError

from .common import AuditCase


class TestAuditSnapshot(AuditCase):

    def setUp(self):
        super().setUp()
        # only the partner configuration counts for these tests, the database may hold real ones
        self.env['audit.model.config'].search([('id', '!=', self.config.id)]).write({'active': False})
        self.admin = self._new_user('audit_snap_admin', 'itc_audit_log.group_audit_admin')
        self.Snapshot = self.env['audit.snapshot'].with_user(self.admin)
        self.snapshot = self.Snapshot.create({'name': 'Départ'})

    def _kinds(self, rows=None):
        rows = self.snapshot._compute_diff() if rows is None else rows
        return [(row['kind'], row['model_name'], row['field_name'], row['attribute']) for row in rows]

    def test_snapshot_contains_only_the_configured_entities_and_all_their_fields(self):
        self.assertEqual(self.snapshot.entity_ids.mapped('model_name'), ['res.partner'])
        real_fields = self.env['ir.model.fields'].search_count([('model_id', '=', self.partner_model.id)])
        self.assertEqual(len(self.snapshot.field_ids), real_fields)

    def test_snapshot_ignores_archived_configurations(self):
        self.config.active = False
        other = self.Snapshot.create({'name': 'Vide'})
        self.assertFalse(other.entity_ids)

    def test_snapshot_shows_how_much_room_it_takes(self):
        self.assertGreater(self.snapshot.storage_bytes, 0)
        self.assertRegex(self.snapshot.storage_size, r'^\d+(\.\d+)? (bytes|Kb|Mb)$')
        self.assertGreater(self.snapshot.storage_bytes, self.Snapshot.create({'name': 'Autre'}).storage_bytes // 2)

    def test_no_difference_right_after_the_snapshot(self):
        self.assertEqual(self._kinds(), [])

    def test_entity_added_to_the_audit(self):
        category = self.env['ir.model']._get('res.partner.category')
        self.env['audit.model.config'].create({'model_id': category.id, 'state': 'running'})
        self.assertIn(('entity_added', 'res.partner.category', '', ''), self._kinds())

    def test_entity_removed_from_the_audit(self):
        self.config.active = False
        self.assertIn(('entity_removed', 'res.partner', '', ''), self._kinds())

    def test_deleted_model_is_told_apart(self):
        self.env['audit.snapshot.entity'].create(
            {'snapshot_id': self.snapshot.id, 'model_name': 'ghost.model', 'model_label': 'Ghost'})
        self.assertIn(('model_deleted', 'ghost.model', '', ''), self._kinds())

    def test_field_added_removed_and_changed(self):
        city = self.snapshot.field_ids.filtered(lambda f: f.field_name == 'city')
        city.ttype = 'text'
        self.snapshot.field_ids.filtered(lambda f: f.field_name == 'zip').unlink()
        self.env['audit.snapshot.field'].create({
            'snapshot_id': self.snapshot.id, 'model_name': 'res.partner', 'field_name': 'ghost_field', 'ttype': 'char'})
        kinds = self._kinds()
        self.assertIn(('field_changed', 'res.partner', 'city', "Type"), kinds)
        self.assertIn(('field_added', 'res.partner', 'zip', ''), kinds)
        self.assertIn(('field_removed', 'res.partner', 'ghost_field', ''), kinds)

    def test_changed_row_gives_old_and_new_values(self):
        self.snapshot.field_ids.filtered(lambda f: f.field_name == 'city').required = 'True'
        row = next(r for r in self.snapshot._compute_diff() if r['field_name'] == 'city')
        self.assertEqual((row['attribute'], row['old_value'], row['new_value']), ("Obligatoire", 'True', ''))

    def test_selection_options_are_compared(self):
        field = self.snapshot.field_ids.filtered(lambda f: f.field_name == 'type')
        field.selection = 'contact=Contact'
        row = next(r for r in self.snapshot._compute_diff() if r['field_name'] == 'type')
        self.assertEqual(row['attribute'], "Options de sélection")

    def test_compare_action_replaces_the_previous_result(self):
        self.snapshot.field_ids.filtered(lambda f: f.field_name == 'city').ttype = 'text'
        self.snapshot.action_compare()
        action = self.snapshot.action_compare()
        rows = self.env['audit.snapshot.diff'].with_user(self.admin).search(action['domain'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.kind, 'field_changed')

    def test_deleting_a_snapshot_removes_its_rows(self):
        entities, fields_rows = self.snapshot.entity_ids, self.snapshot.field_ids
        self.snapshot.unlink()
        self.assertFalse(entities.exists())
        self.assertFalse(fields_rows.exists())

    def test_only_administrators_can_use_snapshots(self):
        viewer = self._new_user('audit_snap_viewer', 'itc_audit_log.group_audit_user')
        with self.assertRaises(AccessError):
            self.env['audit.snapshot'].with_user(viewer).create({'name': 'Interdit'})
        with self.assertRaises(AccessError):
            self.snapshot.with_user(viewer).read(['name'])
