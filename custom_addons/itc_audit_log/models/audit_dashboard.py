from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.tools.misc import human_size

ADMIN_GROUP = 'itc_audit_log.group_audit_admin'
# the choices of the period selector, None means no limit
PERIODS = {'7': 7, '30': 30, '90': 90, 'all': None}


class AuditDashboard(models.AbstractModel):
    # no table: this model only holds the methods the dashboard page calls to get its figures
    _name = 'audit.dashboard'
    _description = "Tableau de bord de la traçabilité"

    # the menu is hidden for other users, but the rule is enforced here on the server
    def _check_admin(self):
        if not self.env.user.has_group(ADMIN_GROUP):
            raise AccessError("Seuls les administrateurs de la traçabilité peuvent ouvrir le tableau de bord.")

    @api.model
    def get_data(self, period='30'):
        self._check_admin()
        if period not in PERIODS:
            period = '30'
        days = PERIODS[period]
        since = fields.Datetime.now() - timedelta(days=days) if days else None
        where, args = ("WHERE date >= %s", (since,)) if since else ("", ())
        cr = self.env.cr
        self.env['audit.log'].flush_model()

        cr.execute("SELECT count(*) FROM audit_log " + where, args)
        entries_count = cr.fetchone()[0]

        # the size is the real disk size of the two tables, it does not depend on the period
        cr.execute("SELECT pg_total_relation_size('audit_log') + pg_total_relation_size('audit_log_line')")
        size_bytes = cr.fetchone()[0]

        cr.execute("SELECT user_id, count(*) FROM audit_log " + where + " GROUP BY user_id ORDER BY 2 DESC LIMIT 5", args)
        top = cr.fetchall()
        users = self.env['res.users'].sudo().with_context(active_test=False).browse([uid for uid, _count in top if uid])
        names = {user.id: user.display_name for user in users}
        top_users = [{'name': names.get(uid, "Utilisateur supprimé"), 'count': count} for uid, count in top]

        cr.execute("""
            SELECT COALESCE(NULLIF(model_label, ''), model_name, '?'), count(*) FROM audit_log
            """ + where + " GROUP BY 1 ORDER BY 2 DESC", args)
        per_entity = cr.fetchall()

        return {
            'period': period,
            'rules_count': self.env['audit.model.config'].search_count([]),
            'entries_count': entries_count,
            'size_bytes': size_bytes,
            'size_label': human_size(size_bytes) or "0 bytes",
            'top_users': top_users,
            'per_day': self._per_day(where, args, since),
            'per_entity': {'labels': [row[0] for row in per_entity], 'values': [row[1] for row in per_entity]},
            'snapshots': [
                {'id': snapshot.id, 'name': snapshot.name, 'date': fields.Datetime.to_string(snapshot.date)}
                for snapshot in self.env['audit.snapshot'].search([])
            ],
        }

    # entries per day, or per month when there is no limit (a day by day chart over years would be unreadable)
    def _per_day(self, where, args, since):
        unit, pattern = ('day', 'YYYY-MM-DD') if since else ('month', 'YYYY-MM')
        self.env.cr.execute(
            "SELECT to_char(date_trunc(%s, date), %s), count(*) FROM audit_log " + where + " GROUP BY 1 ORDER BY 1",
            (unit, pattern) + args)
        counted = dict(self.env.cr.fetchall())
        if since:
            # every day of the period is shown, even the ones without any entry
            day, today = since.date(), fields.Datetime.now().date()
            labels = []
            while day <= today:
                labels.append(day.strftime('%Y-%m-%d'))
                day += timedelta(days=1)
        else:
            labels = sorted(counted)
        return {'unit': unit, 'labels': labels, 'values': [counted.get(label, 0) for label in labels]}

    @api.model
    def compare(self, snapshot_id):
        self._check_admin()
        snapshot = self.env['audit.snapshot'].browse(snapshot_id).exists()
        kinds = dict(self.env['audit.snapshot.diff']._fields['kind'].selection)
        rows = [dict(row, kind_label=kinds[row['kind']]) for row in snapshot._compute_diff()]
        return {'name': snapshot.name, 'rows': rows}
