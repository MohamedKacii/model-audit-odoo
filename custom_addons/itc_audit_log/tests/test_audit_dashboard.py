from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests.common import HttpCase, tagged

from .common import AuditCase


class TestAuditDashboard(AuditCase):

    def setUp(self):
        super().setUp()
        self.admin = self._new_user('audit_dash_admin', 'itc_audit_log.group_audit_admin')
        self.Dashboard = self.env['audit.dashboard'].with_user(self.admin)

    def _age(self, log, days):
        self.env.cr.execute("UPDATE audit_log SET date = %s WHERE id = %s",
                            (fields.Datetime.now() - timedelta(days=days), log.id))
        self.env.invalidate_all()

    def test_kpis(self):
        before = self.Dashboard.get_data('all')
        self.env['res.partner'].create({'name': 'Counted'})
        data = self.Dashboard.get_data('all')
        self.assertEqual(data['entries_count'], before['entries_count'] + 1)
        self.assertEqual(data['rules_count'], self.env['audit.model.config'].search_count([]))
        self.assertGreater(data['size_bytes'], 0)
        self.assertTrue(data['size_label'])

    def test_only_active_rules_are_counted(self):
        before = self.Dashboard.get_data('30')['rules_count']
        self.config.active = False
        self.assertEqual(self.Dashboard.get_data('30')['rules_count'], before - 1)

    def test_period_filters_the_entries(self):
        old = self._logs('create', self.env['res.partner'].create({'name': 'Old one'}).id)
        self._age(old, 40)
        in_30 = self.Dashboard.get_data('30')['entries_count']
        in_90 = self.Dashboard.get_data('90')['entries_count']
        self.assertEqual(in_90, in_30 + self.Log.search_count([('id', '=', old.id)]))

    def test_top_users_are_ranked_and_limited_to_five(self):
        for index in range(6):
            self._partner_as(self._new_user('audit_dash_user_%s' % index), 'Partner %s' % index)
        busy = self._new_user('audit_dash_busy')
        for index in range(3):
            self._partner_as(busy, 'Busy %s' % index)
        top = self.Dashboard.get_data('30')['top_users']
        self.assertLessEqual(len(top), 5)
        self.assertEqual(top, sorted(top, key=lambda row: -row['count']))
        self.assertIn(busy.name, [row['name'] for row in top])

    def test_charts_data(self):
        self.env['res.partner'].create({'name': 'Charted'})
        data = self.Dashboard.get_data('7')
        self.assertEqual(data['per_day']['unit'], 'day')
        self.assertEqual(len(data['per_day']['labels']), 8)
        self.assertEqual(sum(data['per_day']['values']), data['entries_count'])
        self.assertEqual(sum(data['per_entity']['values']), data['entries_count'])
        self.assertIn(self.partner_model.name, data['per_entity']['labels'])
        self.assertEqual(self.Dashboard.get_data('all')['per_day']['unit'], 'month')

    def test_unknown_period_falls_back_to_30_days(self):
        self.assertEqual(self.Dashboard.get_data('nonsense')['period'], '30')

    def test_only_administrators_can_read_the_dashboard(self):
        viewer = self._new_user('audit_dash_viewer', 'itc_audit_log.group_audit_user')
        with self.assertRaises(AccessError):
            self.env['audit.dashboard'].with_user(viewer).get_data('30')
        with self.assertRaises(AccessError):
            self.env['audit.dashboard'].with_user(viewer).compare(1)

    def test_compare_gives_readable_rows(self):
        self.env['audit.model.config'].search([('id', '!=', self.config.id)]).write({'active': False})
        snapshot = self.env['audit.snapshot'].with_user(self.admin).create({'name': 'Dash'})
        snapshot.field_ids.filtered(lambda f: f.field_name == 'city').ttype = 'text'
        result = self.Dashboard.compare(snapshot.id)
        row = next(r for r in result['rows'] if r['field_name'] == 'city')
        self.assertEqual(row['kind_label'], "Champ modifié")
        self.assertEqual(result['name'], 'Dash')

    def test_snapshots_are_listed(self):
        self.env['audit.snapshot'].with_user(self.admin).create({'name': 'Listed'})
        names = [snapshot['name'] for snapshot in self.Dashboard.get_data('30')['snapshots']]
        self.assertIn('Listed', names)


@tagged('post_install', '-at_install', 'itc_audit_log', 'audit_tour')
class TestAuditDashboardTour(HttpCase):
    """Opens the real dashboard in a headless browser, a JavaScript error fails the test."""

    def test_dashboard_tour(self):
        model = self.env['ir.model']._get('res.partner.category')
        self.env['audit.model.config'].create({'model_id': model.id})
        self.env['audit.snapshot'].create({'name': 'Tour'})
        self.start_tour('/web#action=itc_audit_log.dashboard', 'itc_audit_log_dashboard', login='admin')
