from odoo.exceptions import UserError

from .common import AuditCase


class TestAuditChatter(AuditCase):

    def _fresh_config(self):
        # the shared config of the class has a half finished tracking state, a new one starts clean
        config = self.env['audit.model.config'].create({'model_id': self.env['ir.model']._get('res.partner.category').id})
        self.env.cr.precommit.run()
        return config

    def test_configuration_changes_are_tracked(self):
        config = self._fresh_config()
        config.log_write = False
        self.env.cr.precommit.run()
        message = config.message_ids.filtered('tracking_value_ids')[:1]
        self.assertTrue(message)
        self.assertIn('log_write', message.tracking_value_ids.field_id.mapped('name'))

    def test_user_list_changes_are_tracked(self):
        config = self._fresh_config()
        config.excluded_user_ids = self._new_user('audit_tracked_user')
        self.env.cr.precommit.run()
        tracked = config.message_ids.tracking_value_ids.field_id.mapped('name')
        self.assertIn('excluded_user_ids', tracked)

    def test_new_entry_posts_no_message_and_no_follower(self):
        partner = self.env['res.partner'].create({'name': 'Quiet'})
        log = self._logs('create', partner.id)
        self.assertFalse(log.message_ids)
        self.assertFalse(log.message_follower_ids)

    def test_viewer_can_leave_a_note_on_an_entry(self):
        viewer = self._new_user('audit_note_viewer', 'itc_audit_log.group_audit_user')
        viewer.email = 'viewer@example.com'
        log = self._logs('create', self.env['res.partner'].create({'name': 'Noted'}).id)
        log.with_user(viewer).message_post(body="Vérifié, rien d'anormal.", message_type='comment')
        self.assertIn("Vérifié", log.message_ids[:1].body)

    def test_entry_stays_immutable_with_the_chatter(self):
        log = self._logs('create', self.env['res.partner'].create({'name': 'Locked'}).id)
        log.message_post(body="note")
        with self.assertRaises(UserError):
            log.write({'record_name': 'changed'})
        with self.assertRaises(UserError):
            log.unlink()
