from odoo.exceptions import AccessError, UserError, ValidationError


from .common import AuditCase


class TestAuditLog(AuditCase):

    def test_create_is_logged_with_initial_values(self):
        partner = self.env['res.partner'].create({'name': 'Sara', 'email': 'sara@example.com'})
        log = self._logs('create', partner.id)
        self.assertEqual(len(log), 1)
        self.assertEqual(log.user_id, self.env.user)
        self.assertTrue(log.date)
        self.assertEqual(self._line(log, 'email').new_value, 'sara@example.com')
        self.assertEqual(self._line(log, 'name').new_value, 'Sara')

    def test_write_keeps_old_and_new_values(self):
        partner = self.env['res.partner'].create({'name': 'Sara', 'city': 'Alger'})
        partner.write({'city': 'Oran'})
        log = self._logs('write', partner.id)
        self.assertEqual(len(log), 1)
        line = self._line(log, 'city')
        self.assertEqual((line.old_value, line.new_value), ('Alger', 'Oran'))

    def test_write_without_real_change_is_not_logged(self):
        partner = self.env['res.partner'].create({'name': 'Sara', 'city': 'Alger'})
        partner.write({'city': 'Alger'})
        self.assertFalse(self._logs('write', partner.id))

    def test_unlink_is_logged_and_log_survives(self):
        partner = self.env['res.partner'].create({'name': 'Sara', 'city': 'Alger'})
        partner_id = partner.id
        partner.unlink()
        log = self._logs('unlink', partner_id)
        self.assertEqual(len(log), 1)
        self.assertEqual(log.record_name, 'Sara')
        self.assertEqual(self._line(log, 'city').old_value, 'Alger')
        self.assertTrue(self._logs(res_id=partner_id))

    def test_archive_and_unarchive(self):
        partner = self.env['res.partner'].create({'name': 'Sara'})
        partner.write({'active': False})
        partner.write({'active': True})
        archive = self._logs('archive', partner.id)
        unarchive = self._logs('unarchive', partner.id)
        self.assertEqual(self._line(archive, 'active').new_value, 'False')
        self.assertEqual(self._line(unarchive, 'active').new_value, 'True')
        self.assertFalse(self._logs('write', partner.id))

    def test_archive_and_edit_in_one_write_gives_two_logs(self):
        partner = self.env['res.partner'].create({'name': 'Sara', 'city': 'Alger'})
        partner.write({'active': False, 'city': 'Oran'})
        self.assertEqual(len(self._logs('archive', partner.id)), 1)
        self.assertEqual(len(self._logs('write', partner.id)), 1)

    def test_bulk_operations_give_one_log_per_record(self):
        partners = self.env['res.partner'].create([{'name': 'A'}, {'name': 'B'}, {'name': 'C'}])
        ids = partners.ids

        def count(operation):
            return self.Log.search_count([('operation', '=', operation), ('model_name', '=', 'res.partner'),
                                          ('res_id', 'in', ids)])

        self.assertEqual(count('create'), 3)
        partners.write({'city': 'Alger'})
        self.assertEqual(count('write'), 3)
        partners.unlink()
        self.assertEqual(count('unlink'), 3)

    def test_only_selected_fields_are_tracked(self):
        city = self.env['ir.model.fields']._get('res.partner', 'city')
        self.config.write({'track_all_fields': False, 'field_ids': [(6, 0, city.ids)]})
        partner = self.env['res.partner'].create({'name': 'Sara', 'city': 'Alger', 'email': 'a@b.c'})
        log = self._logs('create', partner.id)
        self.assertEqual(log.line_ids.mapped('field_name'), ['city'])
        partner.write({'email': 'x@y.z'})
        self.assertFalse(self._logs('write', partner.id))
        partner.write({'city': 'Oran'})
        self.assertEqual(len(self._logs('write', partner.id)), 1)

    def test_disabled_operation_is_not_logged(self):
        self.config.log_write = False
        partner = self.env['res.partner'].create({'name': 'Sara'})
        partner.write({'city': 'Oran'})
        self.assertTrue(self._logs('create', partner.id))
        self.assertFalse(self._logs('write', partner.id))

    def test_disabled_config_logs_nothing(self):
        self.config.active = False
        partner = self.env['res.partner'].create({'name': 'Sara'})
        self.assertFalse(self._logs(res_id=partner.id))

    def test_unwatched_model_logs_nothing(self):
        before = self.Log.search_count([('model_name', '=', 'res.partner.category')])
        self.env['res.partner.category'].create({'name': 'VIP'})
        self.assertEqual(self.Log.search_count([('model_name', '=', 'res.partner.category')]), before)

    def test_audit_models_cannot_be_watched(self):
        model = self.env['ir.model']._get('audit.log')
        with self.assertRaises(ValidationError):
            self.env['audit.model.config'].create({'model_id': model.id})

    def test_many2one_values_are_readable(self):
        country = self.env.ref('base.dz')
        partner = self.env['res.partner'].create({'name': 'Sara'})
        partner.write({'country_id': country.id})
        line = self._line(self._logs('write', partner.id), 'country_id')
        self.assertEqual(line.new_value, country.display_name)
        self.assertEqual(line.old_value, '')

    def test_binary_fields_are_tracked(self):
        partner = self.env['res.partner'].create({'name': 'Sara'})
        pixel = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABh6FO1AAAAABJRU5ErkJggg=='
        partner.write({'image_1920': pixel})
        log = self._logs('write', partner.id)
        self.assertTrue(log.line_ids.filtered(lambda line: line.field_name == 'image_1920'))

    def test_logs_cannot_be_changed_or_deleted(self):
        partner = self.env['res.partner'].create({'name': 'Sara'})
        log = self._logs('create', partner.id)
        with self.assertRaises(UserError):
            log.unlink()
        with self.assertRaises(UserError):
            log.write({'record_name': 'x'})
        with self.assertRaises(UserError):
            log.line_ids.unlink()

    def test_security_groups(self):
        viewer = self.env['res.users'].create({
            'name': 'Viewer', 'login': 'audit_viewer',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('itc_audit_log.group_audit_user').id])],
        })
        partner = self.env['res.partner'].create({'name': 'Sara'})
        log = self._logs('create', partner.id)
        self.assertTrue(log.with_user(viewer).read(['record_name']))
        with self.assertRaises(AccessError):
            self.env['audit.model.config'].with_user(viewer).create({'model_id': self.env['ir.model']._get('res.users').id})
        with self.assertRaises(AccessError):
            self.Log.with_user(viewer).create({'operation': 'create'})
        log_as_viewer = log.with_user(viewer)
        self.assertFalse(log_as_viewer.check_access_rights('write', raise_exception=False))
        self.assertFalse(log_as_viewer.check_access_rights('unlink', raise_exception=False))
