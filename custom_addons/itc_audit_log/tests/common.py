from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'itc_audit_log')
class AuditCase(TransactionCase):
    """Shared setup: a configuration watching res.partner, with a clean slate."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env['ir.model']._get('res.partner')
        # a real configuration may already exist in the database, the test works on its own copy (rolled back)
        cls.env['audit.model.config'].with_context(active_test=False).search(
            [('model_id', '=', cls.partner_model.id)]).unlink()
        cls.config = cls.env['audit.model.config'].create({'model_id': cls.partner_model.id, 'state': 'running'})
        cls.Log = cls.env['audit.log']

    def _logs(self, operation=None, res_id=None):
        domain = [('model_name', '=', 'res.partner')]
        if operation:
            domain.append(('operation', '=', operation))
        if res_id:
            domain.append(('res_id', '=', res_id))
        return self.Log.search(domain)

    def _line(self, log, field_name):
        return log.line_ids.filtered(lambda line: line.field_name == field_name)

    def _new_user(self, login, *group_xmlids):
        groups = [self.env.ref('base.group_user').id] + [self.env.ref(xmlid).id for xmlid in group_xmlids]
        return self.env['res.users'].create({
            'name': login, 'login': login, 'groups_id': [(6, 0, groups)],
        })

    def _partner_as(self, user, name='Sara'):
        # sudo keeps the uid, so the hook sees the right acting user without being blocked by access rights
        return self.env['res.partner'].with_user(user).sudo().create({'name': name})
