from .common import AuditCase


class TestAuditState(AuditCase):

    def setUp(self):
        super().setUp()
        self.category_model = self.env['ir.model']._get('res.partner.category')
        self.draft = self.env['audit.model.config'].create({'model_id': self.category_model.id})

    def _category_logs(self):
        return self.Log.search([('model_name', '=', 'res.partner.category')])

    def _create_category(self, name):
        self.env['res.partner.category'].create({'name': name})

    def test_a_new_configuration_starts_as_draft(self):
        self.assertEqual(self.draft.state, 'draft')

    def test_draft_audits_nothing(self):
        self._create_category('Draft')
        self.assertFalse(self._category_logs())

    def test_the_buttons_walk_through_the_states(self):
        self.draft.action_start()
        self.assertEqual(self.draft.state, 'running')
        self.draft.action_suspend()
        self.assertEqual(self.draft.state, 'suspended')
        self.draft.action_resume()
        self.assertEqual(self.draft.state, 'running')
        self.draft.action_cancel()
        self.assertEqual(self.draft.state, 'cancelled')
        self.draft.action_draft()
        self.assertEqual(self.draft.state, 'draft')

    def test_only_running_audits(self):
        self.draft.action_start()
        self._create_category('Running')
        self.assertEqual(len(self._category_logs()), 1)
        self.draft.action_suspend()
        self._create_category('Suspended')
        self.assertEqual(len(self._category_logs()), 1)
        self.draft.action_resume()
        self._create_category('Resumed')
        self.assertEqual(len(self._category_logs()), 2)
        self.draft.action_cancel()
        self._create_category('Cancelled')
        self.assertEqual(len(self._category_logs()), 2)

    def test_clicking_a_step_of_the_status_bar_works_like_the_buttons(self):
        self.draft.write({'state': 'running'})
        self._create_category('Clicked')
        self.assertTrue(self._category_logs())
        self.draft.write({'state': 'cancelled'})
        self._create_category('Clicked again')
        self.assertEqual(len(self._category_logs()), 1)

    def test_state_changes_are_tracked_in_the_chatter(self):
        self.env.cr.precommit.run()
        self.draft.action_start()
        self.env.cr.precommit.run()
        tracked = self.draft.message_ids.tracking_value_ids.field_id.mapped('name')
        self.assertIn('state', tracked)

    def test_only_running_configurations_are_in_a_snapshot(self):
        self.env['audit.model.config'].search([('id', 'not in', (self.config.id, self.draft.id))]).write({'active': False})
        snapshot = self.env['audit.snapshot'].create({'name': 'States'})
        self.assertEqual(snapshot.entity_ids.mapped('model_name'), ['res.partner'])
        self.draft.action_start()
        self.assertIn(('entity_added', 'res.partner.category', '', ''),
                      [(r['kind'], r['model_name'], r['field_name'], r['attribute']) for r in snapshot._compute_diff()])
        self.draft.action_suspend()
        self.assertFalse(snapshot._compute_diff())
