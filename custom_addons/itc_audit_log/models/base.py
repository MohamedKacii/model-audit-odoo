from odoo import api, fields, models
from odoo.tools.sql import table_exists

# technical fields (about the record) that we dont detail, the log already has the user and the date
MAGIC_FIELDS =('id', 'create_uid', 'create_date', 'write_uid', 'write_date', '__last_update', 'display_name')
# passwords are never stored in the log, we show stars instead
SENSITIVE_FIELDS =('password', 'password_crypt', 'new_password')


class Base(models.AbstractModel):
    # inheriting base puts this code on every model of the erp, the config decides which ones are really logged ,
    # we do this instead of overriding every single module + the ones we don't know yet , and we need to override the create write and all to modify the logic
    # into what our module is about

    _inherit = 'base'

    @api.model_create_multi
    def create(self, vals_list):
        # create first so the new records get their ids, then we log them
        records = super().create(vals_list)
        config = records._audit_config()
        if config and config['create']:
            names = records._audit_names(config)
            snapshot = records._audit_read(names)
            rows = []
            for record in records:
                lines = [(name, '', text) for name, text in snapshot[record.id].items() if text]
                rows.append((record.id, record.sudo().display_name, lines))
            records._audit_create_logs('create', rows)
        return records


    def write(self, vals):
        # model not watched, nothing to do
        config = self._audit_config()
        if not config or not self:
            return super().write(vals)

        watch_active = config['archive'] and 'active' in vals and 'active' in self._fields
        names = [name for name in self._audit_names(config) if name in vals and name != 'active']
        watch_write = config['write'] and names

        # old values must be read BEFORE the real write, afterwards they are gone
        before = self._audit_read(names) if watch_write else {}
        old_active = {record.id: record.active for record in self.sudo()} if watch_active else {}

        result = super().write(vals)

        # archive/unarchive gets its own log, separate from the field changes
        if watch_active:
            archived, unarchived = [], []
            for record in self.sudo():
                if old_active[record.id] != record.active:
                    line = [('active', str(old_active[record.id]), str(record.active))]
                    row = (record.id, record.display_name, line)
                    (unarchived if record.active else archived).append(row)
            if archived:
                self._audit_create_logs('archive', archived)
            if unarchived:
                self._audit_create_logs('unarchive', unarchived)

        if watch_write:
            # compare before/after and keep only the fields that really changed
            after = self._audit_read(names)
            rows = []
            for record in self.sudo():
                lines = [(name, before[record.id][name], after[record.id][name])
                         for name in names if before[record.id][name] != after[record.id][name]]
                if lines:
                    rows.append((record.id, record.display_name, lines))
            if rows:
                self._audit_create_logs('write', rows)
        return result

    def unlink(self):
        config = self._audit_config()
        rows = []
        # take a snapshot before the delete, after it the data is gone
        if config and config['unlink'] and self:
            snapshot = self._audit_read(self._audit_names(config))
            for record in self.sudo():
                lines = [(name, text, '') for name, text in snapshot[record.id].items() if text]
                rows.append((record.id, record.display_name, lines))
        # the log is written after super so a failed delete leaves no log
        result = super().unlink()
        if rows:
            self._audit_create_logs('unlink', rows)
        return result

#decides wether to audit a MODEL or not
    def _audit_config(self):
        # never audit this module's own models  (audit_log , audit_log_line , audit_model_config ), otherwise infinite loop
        if self._name.startswith('audit.') or self.env.context.get('audit_skip'):
            return None
        # during install the audit tables dont exist yet, so we wait until they do
        registry = self.env.registry
        if not getattr(registry, '_audit_ready', False):
            if 'audit.model.config' not in registry or not table_exists(self.env.cr, 'audit_model_config'):
                return None
            registry._audit_ready = True
        config = self.env['audit.model.config'].sudo()._get_config(self._name)
        if not config:
            return None
        # the rule only counts inside its period and for the users it targets, checked now because the config is cached
        now = fields.Datetime.now()
        if config['date_start'] and now < config['date_start']:
            return None
        if config['date_end'] and now > config['date_end']:
            return None
        # all_users on: the listed users are the excluded ones, all_users off: the listed users are the only ones audited
        listed = self.env.uid in config['users']
        if listed == config['all_users']:
            return None
        return config

#decides which FIELDS to log
    def _audit_names(self, config):
        # fields we log: stored ones + one2many, minus the technical ones, filtered by the config
        tracked = config['fields']
        names = []
        for name, field in self._fields.items():
            if name in MAGIC_FIELDS:
                continue
            if not (field.store or field.type == 'one2many'):
                continue
            if tracked is None or name in tracked:
                names.append(name)
        return names

# sudo so access rights dont block the read, bin_size off to get the real binary content and not just its size
    def _audit_read(self, names):
        result = {}
        for record in self.sudo().with_context(bin_size=False):
            result[record.id] = {name: record._audit_text(name) for name in names}
        return result

# turns the value of any field type into plain text for the log
    def _audit_text(self, name):
        if name in SENSITIVE_FIELDS:
            return '********'
        field = self._fields[name]
        value = self[name]
        if field.type == 'many2one':
            return value.display_name or ''
        if field.type in ('one2many', 'many2many'):
            return ', '.join(item.display_name or str(item.id) for item in value)
        if field.type == 'selection':
            return dict(field._description_selection(self.env)).get(value, value) or ''
        if field.type == 'binary':
            return value.decode() if isinstance(value, bytes) else ''
        if field.type == 'boolean':
            return str(value)
        return str(value) if value not in (False, None) else ''


# creates the audit log for audit log model , constructs the entry using a dictionary in vals list
# and then appends it in the orm by doing self.env , we use sudo because normal users don't have permissions

    def _audit_create_logs(self, operation, rows):

        model = self.env['ir.model']._get(self._name)
        vals_list = []
        for res_id, record_name, lines in rows:
            vals_list.append({
                'user_id': self.env.uid,
                'model_name': self._name,
                'model_label': model.name or self._name,
                'res_id': res_id,
                'record_name': record_name,
                'operation': operation,
                'line_ids': [(0, 0, {
                    'field_name': name,
                    'field_label': self._fields[name].string if name in self._fields else name,
                    'old_value': old,
                    'new_value': new,
                }) for name, old, new in lines],
            })
        # no "created" message, no tracking and no follower for each entry, otherwise the chatter would add rows on every log
        self.env['audit.log'].sudo().with_context(
            mail_create_nolog=True, mail_create_nosubscribe=True, mail_notrack=True).create(vals_list)
