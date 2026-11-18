# itc_audit_log v2: specification

Status: implemented (see the tests in `tests/`).
Vocabulary: see [CONTEXT.md](../CONTEXT.md). UI text is in French, code is in English.

## 1. Goal

Extend the existing module (journal of create / write / delete / archive operations) with:

1. Chatter on the module's forms.
2. Per-user and per-period auditing, set on each configuration.
3. An administrator dashboard (KPIs, two charts, shortcuts).
4. A purge of old entries, administrators only, always traced.
5. Schema snapshots and a comparison of the current schema against a snapshot.

## 2. Constraints

- **Pluggable.** The module installs on any standard Odoo 17 database. It depends on `base` and `mail` only, both shipped with every Odoo edition. No Enterprise module, no third-party module, no external Python library.
- **Independent.** Nothing in `itc_audit_log` references `first_module` or any other custom module.
- **Charts** use the Chart.js copy already bundled in Odoo's `web` addon, not a download.
- **One configuration per entity** stays (the model `audit.model.config` and the "Configuration" menu keep their names).

## 3. Chatter

- Added to every **persistent** form of the module: configuration, entry (audit.log), snapshot, purge trace.
- Includes messages, log notes, activities and followers (`mail.thread` + `mail.activity.mixin`).
- **Exceptions:** the dashboard and the comparison screen are not stored records, so they cannot have a chatter.
- **Configuration:** every field is tracked (`tracking=True`), so each edit shows "old → new" in the chatter, like the standard Odoo behaviour. Odoo 17 supports tracking on many2many fields, so the user lists are tracked the same way.
- **Entries are immutable but can carry notes:**
  - A user of the group Utilisateur can post messages and notes on an entry even though the entry is read-only (`_mail_post_access = 'read'`).
  - Creating an entry must not post a "created" message (`mail_create_nolog`).
  - The write block on `audit.log` must still let Odoo's own technical mail fields through (for example `message_main_attachment_id`), otherwise posting an attachment crashes. Everything else stays blocked.

## 4. Per-user and per-period configuration

New fields on `audit.model.config`:

| Field | Meaning |
| --- | --- |
| `audit_all_users` (Boolean, default True) | "Auditer tous les utilisateurs" |
| `excluded_user_ids` (Many2many res.users) | "Sauf", shown when the toggle is on |
| `included_user_ids` (Many2many res.users) | "Utilisateurs audités", shown when the toggle is off |
| `date_start`, `date_end` (Datetime, both optional) | Audit period |
| status (computed, not stored) | En attente / En cours / Terminée |

Use two separate relation tables for the two many2many fields.

**Matching, evaluated when an operation happens** (never cached, because it depends on the current time and user):

1. The entity has an active configuration.
2. Now is inside the period (an empty start or end means open-ended).
3. The acting user is allowed: toggle on means "not in excluded"; toggle off means "in included".

The acting user is `env.uid`. Scheduled jobs and OdooBot are ordinary users: they are logged (shown as OdooBot) unless excluded.

**Validation:**
- Toggle off requires at least one included user.
- `date_end` must be after `date_start`.
- A start or end date cannot be in the past **when it is set or changed**. Editing other fields of a running configuration is allowed.
- No scheduled job: outside its period a configuration is simply ignored.

**Migration:** existing configurations get toggle on, empty "sauf" list, no dates (same behaviour as today).

**Views:** status badge in the list, ribbon for archived, the user fields switch with the toggle.

## 5. Dashboard

Menu **Traçabilité > Tableau de bord**, first entry, **Administrateur only** (enforced on the server, not only by hiding the menu).

Built as a client action (OWL) because the standard Community views cannot embed charts in a page. All figures and all rules stay in Python and are fetched by RPC.

- **Period selector:** 7, 30, 90 days or all. Default 30.
- **KPIs:**
  - Number of **active** configurations (not affected by the period).
  - Number of entries in the period.
  - **Journal size**: disk size in MB of the entry and detail tables (not affected by the period).
  - **Top 5 audited users** in the period, with their number of entries.
- **Charts:** entries per day (per month when the period is "all"), and entries per entity.
- **Buttons:** voir le journal, aller à la configuration, purger les logs (the last one opens the purge wizard).
- **Snapshot comparison:** a list of snapshots, a "Comparer" button, and the differences shown on the dashboard (section 7).

## 6. Purge

Decision recorded in [ADR 0001](adr/0001-purge-of-audit-entries.en.md).

- Administrateur only.
- A wizard asks for a **cutoff date and time** (not in the future). It shows how many entries would be deleted, then asks for a final confirmation.
- It deletes entries older than the cutoff, with their details.
- The immutability rule stays for every other path. The purge uses one dedicated, private method.
- Each purge writes a **purge trace** (`audit.purge`): who, when, cutoff, number of entries deleted. Traces are read-only, cannot be purged, and have a chatter.
- Menu **Traçabilité > Historique des purges**, Administrateur only.

## 7. Schema snapshot and comparison

**Scope:** only entities that have an active configuration at the moment of the snapshot. All fields of each of those entities, not only the fields its configuration tracks.

**Taking a snapshot:** a button creates a record with a name, a date and the user, plus one row per entity and one row per field.

**Compared properties** for a field: type, label, required, read-only, stored or computed, relation target, selection options.

**Comparison** (current schema against a chosen snapshot) produces difference rows:

- entity added to the audit, or removed from the audit (or model deleted from Odoo);
- field added or removed;
- field property changed, with old and new value.

The result is generated on demand and not stored. It can be filtered and exported to Excel.

**Size:** the snapshot's details page shows how much space it takes (sum of the stored size of its rows, shown in KB or MB). The list shows it too.

**Deletion:** administrators can delete snapshots (they are not audit entries). Administrateur only for taking, comparing and deleting.

Where it lives: menu **Traçabilité > Instances**, plus the comparison panel in the dashboard.

## 8. Security

| Item | Utilisateur | Administrateur |
| --- | --- | --- |
| Journal (entries, details) | read, can post notes | read, can post notes |
| Configuration | read | read, write, create, delete |
| Dashboard | no | yes |
| Snapshots and comparison | no | yes |
| Purge wizard and history | no | yes |

No one can edit or delete an entry through the interface or the standard ORM. Only the purge can delete, and it leaves a trace.

## 9. Menus

Traçabilité: Tableau de bord, Journal des opérations, Configuration, Instances, Historique des purges.

## 10. Tests to add

- User matching: only included users, all except excluded users, OdooBot, empty included list refused.
- Period: before start, inside, after end, open-ended; past-date validation; status badge.
- Chatter: tracked configuration changes post a message; a note can be posted on an entry by a Utilisateur; creating an entry posts nothing.
- Purge: only older entries deleted, trace written, non-admin refused, future cutoff refused, entries not purgeable any other way.
- Snapshot: only configured entities included, size computed, each kind of difference detected, comparison not stored.
- Dashboard data: KPI values, period filter, admin-only access on the server.

## 11. Implementation order

1. Per-user and per-period configuration (changes the hook, so it comes first).
2. Chatter on the existing forms.
3. Purge, purge trace, ADR.
4. Snapshot and comparison.
5. Dashboard last, since it displays everything above.
6. Update the user guide (French) and the tests as each step lands.

## 12. Decisions taken without asking you

Say so if any is wrong.

- **Dashboard in JavaScript.** You said JavaScript for pure views and native for business rules. The standard Community views cannot embed charts in a form, so the dashboard is a hybrid: JavaScript draws the page, Python holds all figures and rules. This replaces my earlier "native" answer.
- **Chatter scope.** All persistent forms of this module only. `first_module` is untouched, and no shared mixin is added, so the module stays independent.
- **Dashboard and comparison screen** have no chatter (they are not stored records).
- **Snapshots, comparison and dashboard** are Administrateur only.
- **Top users** means the users who performed the most audited actions. **Journal size** means disk size.
- **System actions** (cron, OdooBot) are logged unless excluded.

## 13. Out of scope

- Several periods or several user lists for the same entity at the same time.
- Auditing by role or group.
- Chatter on forms of other modules.
- Enterprise-only dashboard views.

## 14. Risks to check while building

Checked while building:
- Tracking on many2many fields works in Odoo 17.
- `mail.thread` on a model whose `write` is blocked works once the write guard lets `message_main_attachment_id` through.
- The bundled Chart.js loads from a client action (`/web/static/lib/Chart/Chart.js`).
- Wizard and comparison models need access rules in Odoo 17, even though they are transient. They are given to the Administrateur group only.
- Archived users (OdooBot) are hidden from many2many fields unless `active_test` is off, so the two user lists switch it off.
- A past-date check allows one minute of tolerance, because the date picker only has minutes.
