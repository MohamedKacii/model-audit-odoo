from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError

from .common import AuditCase


class TestAuditPurge(AuditCase):

    def setUp(self):
        super().setUp()
        self.admin = self._new_user('audit_purge_admin', 'itc_audit_log.group_audit_admin')
        self.admin.email = 'purge.admin@example.com'

    def _age(self, log, days):
        # entries cannot be edited, so the date is moved with sql to simulate old entries
        self.env.cr.execute("UPDATE audit_log SET date = %s WHERE id = %s",
                            (fields.Datetime.now() - timedelta(days=days), log.id))
        self.env.invalidate_all()

    def _purge(self, user, cutoff):
        wizard = self.env['audit.purge.wizard'].with_user(user).create({'cutoff': cutoff})
        return wizard, wizard.action_purge()

    def test_purge_deletes_only_older_entries_with_their_details(self):
        old = self._logs('create', self.env['res.partner'].create({'name': 'Old', 'city': 'Alger'}).id)
        recent = self._logs('create', self.env['res.partner'].create({'name': 'Recent'}).id)
        old_lines = old.line_ids
        self._age(old, 10)
        cutoff = fields.Datetime.now() - timedelta(days=5)
        self._purge(self.admin, cutoff)
        self.assertFalse(old.exists())
        self.assertFalse(old_lines.exists())
        self.assertTrue(recent.exists())

    def test_purge_removes_the_chatter_of_deleted_entries(self):
        old = self._logs('create', self.env['res.partner'].create({'name': 'Noted'}).id)
        old.message_post(body="à vérifier")
        message_ids = old.message_ids.ids
        self._age(old, 10)
        self._purge(self.admin, fields.Datetime.now() - timedelta(days=5))
        self.assertFalse(self.env['mail.message'].browse(message_ids).exists())

    def test_purge_leaves_a_trace(self):
        old = self._logs('create', self.env['res.partner'].create({'name': 'Traced'}).id)
        self._age(old, 10)
        cutoff = fields.Datetime.now() - timedelta(days=5)
        _wizard, action = self._purge(self.admin, cutoff)
        trace = self.env['audit.purge'].browse(action['res_id'])
        self.assertEqual(trace.user_id, self.admin)
        self.assertEqual(trace.cutoff, cutoff)
        self.assertGreaterEqual(trace.entries_count, 1)

    def test_wizard_counts_the_entries_before_deleting(self):
        old = self._logs('create', self.env['res.partner'].create({'name': 'Counted'}).id)
        self._age(old, 10)
        wizard = self.env['audit.purge.wizard'].with_user(self.admin).create(
            {'cutoff': fields.Datetime.now() - timedelta(days=5)})
        self.assertGreaterEqual(wizard.entries_count, 1)
        self.assertTrue(old.exists())

    def test_traces_cannot_be_edited_or_deleted(self):
        _wizard, action = self._purge(self.admin, fields.Datetime.now() - timedelta(days=5))
        trace = self.env['audit.purge'].browse(action['res_id'])
        with self.assertRaises(UserError):
            trace.write({'entries_count': 0})
        with self.assertRaises(UserError):
            trace.unlink()

    def test_future_cutoff_is_refused(self):
        wizard = self.env['audit.purge.wizard'].with_user(self.admin).create(
            {'cutoff': fields.Datetime.now() + timedelta(days=1)})
        with self.assertRaises(UserError):
            wizard.action_purge()

    def test_only_administrators_can_purge(self):
        viewer = self._new_user('audit_purge_viewer', 'itc_audit_log.group_audit_user')
        with self.assertRaises(AccessError):
            self.env['audit.purge.wizard'].with_user(viewer).create(
                {'cutoff': fields.Datetime.now() - timedelta(days=5)})

    def test_the_wizard_checks_the_group_itself_even_with_access(self):
        viewer = self._new_user('audit_purge_viewer3', 'itc_audit_log.group_audit_user')
        wizard = self.env['audit.purge.wizard'].create({'cutoff': fields.Datetime.now() - timedelta(days=5)})
        with self.assertRaises(AccessError):
            wizard.with_user(viewer).action_purge()

    def test_the_private_method_checks_the_group_too(self):
        viewer = self._new_user('audit_purge_viewer2', 'itc_audit_log.group_audit_user')
        with self.assertRaises(AccessError):
            self.env['audit.log'].with_user(viewer)._purge_before(fields.Datetime.now())

    def test_entries_stay_undeletable_by_the_orm(self):
        log = self._logs('create', self.env['res.partner'].create({'name': 'Protected'}).id)
        with self.assertRaises(UserError):
            log.unlink()
