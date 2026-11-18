from datetime import timedelta

from odoo import api, fields, models, tools
from odoo.exceptions import ValidationError

# the date picker only has minutes, so "now" picked by the user is a few seconds in the past by the time it is saved
PAST_TOLERANCE = timedelta(minutes=1)


class AuditModelConfig(models.Model):
    _name = 'audit.model.config'
    # chatter: messages, notes, activities and followers on the configuration form
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Configuration de traçabilité d'un modèle"
    _rec_name = 'model_id'

    # the model we watch, if that model disappears its config goes with it (cascade)
    model_id = fields.Many2one(
        'ir.model', string="Modèle", required=True, ondelete='cascade',
        domain=[('transient', '=', False)], tracking=True)

    active = fields.Boolean(string="Actif", default=True, tracking=True) # this triggers an archive button to be made
    # one switch per type of operation, the admin picks which ones get logged
    log_create = fields.Boolean(string="Création", default=True, tracking=True)
    log_write = fields.Boolean(string="Modification", default=True, tracking=True)
    log_unlink = fields.Boolean(string="Suppression", default=True, tracking=True)
    log_archive = fields.Boolean(string="Archivage / Désarchivage", default=True, tracking=True)
    # ticked = every field is tracked, unticked = only the ones in field_ids
    track_all_fields = fields.Boolean(string="Suivre tous les champs", default=True, tracking=True)

    # only used when track_all_fields is off, the domain shows just the fields of the chosen model
    field_ids = fields.Many2many(
        'ir.model.fields', string="Champs suivis",
        domain="[('model_id', '=', model_id)]", tracking=True)

    # ticked = everybody is audited except excluded_user_ids, unticked = only included_user_ids are audited
    audit_all_users = fields.Boolean(string="Auditer tous les utilisateurs", default=True, tracking=True)
    # two relation tables because both lists point to res.users, active_test off so archived users like OdooBot can be picked
    excluded_user_ids = fields.Many2many(
        'res.users', 'audit_config_excluded_user_rel', 'config_id', 'user_id',
        string="Sauf ces utilisateurs", tracking=True, context={'active_test': False})
    included_user_ids = fields.Many2many(
        'res.users', 'audit_config_included_user_rel', 'config_id', 'user_id',
        string="Utilisateurs audités", tracking=True, context={'active_test': False})

    # the audit period, both optional: only a start = from then on, only an end = until then, none = always
    date_start = fields.Datetime(string="Début de l'audit", tracking=True)
    date_end = fields.Datetime(string="Fin de l'audit", tracking=True)
    # not stored on purpose, it depends on the current time so it is worked out each time it is read
    # this one only says where we are in the dates, the lifecycle chosen by the admin is the state field below
    status = fields.Selection([
        ('pending', "Pas commencée"),
        ('running', "Active"),
        ('done', "Terminée"),
    ], string="Période", compute='_compute_status')

    # the lifecycle of the configuration, shown as a clickable status bar: only "En cours" audits something
    state = fields.Selection([
        ('draft', "Brouillon"),
        ('running', "En cours"),
        ('suspended', "Suspendu"),
        ('cancelled', "Annulé"),
    ], string="État", default='draft', required=True, copy=False, tracking=True)

# we did this constraint to not have a second model configuration that we already have done , ( no conflicts )
    _sql_constraints = [
        ('model_unique', 'unique(model_id)', "Ce modèle a déjà une configuration."),
    ]

#audit cannot track audit modules otherwise it'll be a never ending loop
    @api.constrains('model_id')
    def _check_model_allowed(self):
        for config in self:
            if config.model_id.model.startswith('audit.'):
                raise ValidationError("Les modèles du journal d'audit ne peuvent pas être surveillés.")

    # when we audit only some users the list cannot be empty, otherwise nobody would be audited
    @api.constrains('audit_all_users', 'included_user_ids')
    def _check_included_users(self):
        for config in self:
            if not config.audit_all_users and not config.included_user_ids:
                raise ValidationError("Choisissez au moins un utilisateur à auditer, ou cochez « Auditer tous les utilisateurs ».")

    @api.constrains('date_start', 'date_end')
    def _check_dates_order(self):
        for config in self:
            if config.date_start and config.date_end and config.date_end <= config.date_start:
                raise ValidationError("La date de fin doit être après la date de début.")

    # one method per button of the status bar, each one just moves the configuration to another state
    def action_start(self):
        self.write({'state': 'running'})

    def action_suspend(self):
        self.write({'state': 'suspended'})

    def action_resume(self):
        self.write({'state': 'running'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'draft'})

    @api.depends('date_start', 'date_end')
    def _compute_status(self):
        now = fields.Datetime.now()
        for config in self:
            if config.date_start and now < config.date_start:
                config.status = 'pending'
            elif config.date_end and now > config.date_end:
                config.status = 'done'
            else:
                config.status = 'running'

    # a date cannot be set in the past, but only when it is new or changed, so a running config can still be edited
    def _check_not_in_past(self, vals):
        limit = fields.Datetime.now() - PAST_TOLERANCE
        for name in ('date_start', 'date_end'):
            if not vals.get(name):
                continue
            value = fields.Datetime.to_datetime(vals[name])
            if value >= limit:
                continue
            if self and all(record[name] == value for record in self):
                continue
            raise ValidationError("Les dates de l'audit ne peuvent pas être dans le passé.")

    # gives the settings of one model as a dictionary ( if  watched), cached because it runs on every create/write/unlink of the erp
    @api.model
    @tools.ormcache('model_name')
    def _get_config(self, model_name):
        # a configuration only audits while its state is "En cours" (draft, suspended and cancelled ones are ignored)
        config = self.search([('model_id.model', '=', model_name), ('state', '=', 'running')], limit=1)
        if not config:
            return None
        users = config.excluded_user_ids if config.audit_all_users else config.included_user_ids
        return {
            'create': config.log_create,
            'write': config.log_write,
            'unlink': config.log_unlink,
            'archive': config.log_archive,
            'fields': None if config.track_all_fields else frozenset(config.field_ids.mapped('name')),
            'all_users': config.audit_all_users,
            'users': frozenset(users.ids),
            'date_start': config.date_start,
            'date_end': config.date_end,
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_not_in_past(vals)
        # wipe the cache AFTER the change so a config change applies right away (same in write and unlink)
        records = super().create(vals_list)
        self.env.registry.clear_cache()
        return records

    def write(self, vals):
        self._check_not_in_past(vals)
        result = super().write(vals)
        self.env.registry.clear_cache()
        return result

    def unlink(self):
        result = super().unlink()
        self.env.registry.clear_cache()
        return result
