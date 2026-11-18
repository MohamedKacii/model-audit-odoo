from datetime import timedelta
from unittest.mock import patch

from odoo import SUPERUSER_ID, fields
from odoo.exceptions import ValidationError

from .common import AuditCase


class TestAuditUsers(AuditCase):

    def test_everyone_is_audited_by_default(self):
        user = self._new_user('audit_any_user')
        partner = self._partner_as(user)
        self.assertEqual(self._logs('create', partner.id).user_id, user)

    def test_excluded_user_is_not_logged_but_others_are(self):
        excluded = self._new_user('audit_excluded')
        other = self._new_user('audit_other')
        self.config.excluded_user_ids = excluded
        self.assertFalse(self._logs('create', self._partner_as(excluded).id))
        self.assertTrue(self._logs('create', self._partner_as(other).id))

    def test_only_included_users_are_logged(self):
        included = self._new_user('audit_included')
        other = self._new_user('audit_not_included')
        self.config.write({'audit_all_users': False, 'included_user_ids': [(6, 0, included.ids)]})
        self.assertTrue(self._logs('create', self._partner_as(included).id))
        self.assertFalse(self._logs('create', self._partner_as(other).id))

    def test_included_users_cannot_be_empty(self):
        with self.assertRaises(ValidationError):
            self.config.audit_all_users = False

    def test_system_user_is_logged_as_odoobot(self):
        partner = self.env['res.partner'].with_user(SUPERUSER_ID).create({'name': 'Cron made'})
        self.assertEqual(self._logs('create', partner.id).user_id.id, SUPERUSER_ID)

    def test_system_user_can_be_excluded(self):
        self.config.excluded_user_ids = self.env.ref('base.user_root')
        partner = self.env['res.partner'].with_user(SUPERUSER_ID).create({'name': 'Cron made'})
        self.assertFalse(self._logs('create', partner.id))


class TestAuditPeriod(AuditCase):

    def _later(self, **delta):
        return fields.Datetime.now() + timedelta(**delta)

    def test_period_not_started_logs_nothing(self):
        self.config.date_start = self._later(days=1)
        partner = self.env['res.partner'].create({'name': 'Early'})
        self.assertFalse(self._logs('create', partner.id))
        self.assertEqual(self.config.status, 'pending')

    def test_inside_the_period_logs(self):
        self.config.write({'date_start': self._later(days=1), 'date_end': self._later(days=2)})
        with patch.object(fields.Datetime, 'now', return_value=self._later(days=1, hours=5)):
            partner = self.env['res.partner'].create({'name': 'Inside'})
            self.assertEqual(self.config.status, 'running')
        self.assertTrue(self._logs('create', partner.id))

    def test_after_the_end_logs_nothing(self):
        self.config.date_end = self._later(days=1)
        with patch.object(fields.Datetime, 'now', return_value=self._later(days=2)):
            partner = self.env['res.partner'].create({'name': 'Late'})
            self.assertEqual(self.config.status, 'done')
        self.assertFalse(self._logs('create', partner.id))

    def test_open_ended_period_always_logs(self):
        self.config.date_start = self._later(hours=1)
        with patch.object(fields.Datetime, 'now', return_value=self._later(days=400)):
            partner = self.env['res.partner'].create({'name': 'Much later'})
        self.assertTrue(self._logs('create', partner.id))

    def test_dates_in_the_past_are_refused(self):
        with self.assertRaises(ValidationError):
            self.config.date_start = self._later(days=-1)
        with self.assertRaises(ValidationError):
            self.config.date_end = self._later(hours=-2)

    def test_new_config_with_past_date_is_refused(self):
        model = self.env['ir.model']._get('res.partner.category')
        with self.assertRaises(ValidationError):
            self.env['audit.model.config'].create({'model_id': model.id, 'date_start': self._later(days=-1)})

    def test_running_config_can_still_be_edited(self):
        start, end = self._later(days=1), self._later(days=3)
        self.config.write({'date_start': start, 'date_end': end})
        with patch.object(fields.Datetime, 'now', return_value=self._later(days=2)):
            self.config.log_write = False
            self.config.write({'date_start': start})
            with self.assertRaises(ValidationError):
                self.config.date_start = self._later(days=1, hours=1) - timedelta(days=2)

    def test_end_must_be_after_start(self):
        with self.assertRaises(ValidationError):
            self.config.write({'date_start': self._later(days=2), 'date_end': self._later(days=1)})

    def test_period_change_applies_immediately(self):
        partner = self.env['res.partner'].create({'name': 'Before'})
        self.assertTrue(self._logs('create', partner.id))
        self.config.date_start = self._later(days=1)
        other = self.env['res.partner'].create({'name': 'After'})
        self.assertFalse(self._logs('create', other.id))
