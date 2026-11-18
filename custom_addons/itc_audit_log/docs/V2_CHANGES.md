# itc_audit_log: what changed from v1 to v2 (and why)

Version: manifest `17.0.1.1.0`. Companion to [SPEC.md](SPEC.md) (what was asked), [../DECISIONS.md](../DECISIONS.md) (decisions) and [../CONTEXT.md](../CONTEXT.md) (vocabulary).
This document describes **what was built**, file by file, and explains the Odoo concepts behind each piece.

## 0. How this comparison was made (read first)

The project is **not a git repository** and no copy of v1 was kept, so a real `diff` was impossible. The v1 baseline was reconstructed from:

- [../../../itc_audit_log.puml](../../../itc_audit_log.puml): the v1 class diagram (dated 15 Nov).
- The "Decided (v1, built)" section of [DECISIONS.md](../DECISIONS.md).
- File modification times: `models/audit_log_line.py` (15 Nov 14:12) and the icon are the only files older than the v2 work (16 Nov 09:30 onward). They are unchanged.
- The "Goal" section of the SPEC, which lists exactly what v2 adds to "the existing module".

Treat any statement of the form "v1 had X" as reliable when it comes from the puml or DECISIONS, and as inferred when it comes only from timestamps. Initialise git now (`git init && git add -A && git commit`) so the next comparison is exact.

## 1. Summary

| Area | v1 | v2 |
| --- | --- | --- |
| Dependencies | `base` | `base`, `mail` |
| What is watched | per entity: operations + fields | same, plus **who** (user lists) and **when** (period) |
| Configuration lifecycle | only `active` flag | `state`: Brouillon, En cours, Suspendu, Annulé (clickable status bar). Not in the SPEC, added during build |
| Chatter | none | on configuration, entry, snapshot ("Instance"), purge trace |
| Deleting entries | impossible for everyone | **purge**, admin only, always traced (ADR 0001) |
| Dashboard | graph and pivot views on the journal | OWL client action with KPIs and two Chart.js charts |
| Schema history | none | **snapshot** ("Instance") and comparison against current schema |
| Security groups | Utilisateur, Administrateur | same two groups, more models gated to Administrateur |
| Tests | v1 tests (`test_audit_log.py`) | + rule, chatter, state, purge, snapshot, dashboard, tour |

New models: `audit.purge`, `audit.purge.wizard`, `audit.snapshot`, `audit.snapshot.entity`, `audit.snapshot.field`, `audit.snapshot.diff`, `audit.dashboard`.
Changed models: `audit.model.config`, `audit.log`, and the `base` hook.
Unchanged: `audit.log.line`.

## 2. The core concept: the `base` hook (unchanged idea, changed decision)

[../models/base.py](../models/base.py)

`_inherit = 'base'` on an `AbstractModel` injects `create`, `write` and `unlink` into **every** model of the ERP. Each override calls `self._audit_config()`, which answers "is this model, for this user, right now, watched?". If it returns `None`, the override is a straight pass-through to `super()`. This is why one module can audit any entity, including ones installed later, without touching them.

Order of operations matters and is deliberate:

- **create**: `super()` first (ids needed), then log.
- **write**: read the old values *before* `super().write()`, then read the new values, then log only fields whose text really differs. A write that changes nothing logs nothing. `active` is handled separately so one `write({'active': False, 'name': 'x'})` gives two entries (archive + write).
- **unlink**: read values *before* deleting, write the log *after* `super().unlink()`, so a failed delete leaves no phantom entry.

### What v2 changed in `_audit_config` (the decision point)

v1 decided only on the model. v2 adds two checks, evaluated at operation time:

1. **Period**: `now < date_start` or `now > date_end` returns `None`. An empty bound means open-ended.
2. **User**: the config carries one user set plus a flag. `listed = env.uid in users`. If `listed == all_users` the operation is skipped. Truth table:

| `audit_all_users` | uid in list | audited? |
| --- | --- | --- |
| on (list = excluded) | yes | no |
| on | no | yes |
| off (list = included) | yes | yes |
| off | no | no |

The acting user is `env.uid`. Cron jobs and OdooBot are ordinary users: logged unless excluded. This is why the user fields use `context={'active_test': False}`: OdooBot is an archived user and would otherwise be unselectable.

Why the date/user checks are **not** inside the cached config: see section 3, "Caching".

Also new in `_audit_create_logs`: it stores `model_label` (human name, e.g. "Contact") next to `model_name`, and creates the entry with `mail_create_nolog`, `mail_create_nosubscribe`, `mail_notrack`. Without these flags the chatter would add a "created" message and a follower to every entry, doubling the write cost of every audited operation. `model_label` is used by the dashboard chart. It is not in the v1 puml, so it is probably v2: entries created before the upgrade have it empty, and the dashboard falls back to `model_name` with `COALESCE(NULLIF(model_label,''), model_name)`. The migration does not backfill it.

## 3. Configuration (`audit.model.config`)

[../models/audit_model_config.py](../models/audit_model_config.py), [../views/audit_model_config_views.xml](../views/audit_model_config_views.xml)

### New fields

| Field | Purpose |
| --- | --- |
| `audit_all_users` | toggle, default on |
| `excluded_user_ids` | "Sauf ces utilisateurs", used when toggle on |
| `included_user_ids` | "Utilisateurs audités", used when toggle off |
| `date_start`, `date_end` | optional period |
| `status` | computed, **not stored**: Pas commencée / Active / Terminée (from dates only) |
| `state` | stored lifecycle: draft / running / suspended / cancelled, default `draft`, `copy=False` |

Two Many2many fields to `res.users` need **two explicit relation tables** (`audit_config_excluded_user_rel`, `audit_config_included_user_rel`). Without explicit names Odoo would derive the same table for both and they would overwrite each other.

`status` (dates) and `state` (admin decision) are deliberately separate concepts and were renamed in the UI ("Période" vs "État") so they are not confused. A config audits only when `state == 'running'` **and** the date window is open **and** the user matches.

### Lifecycle (`state`)

Buttons: Démarrer (draft to running), Suspendre (running to suspended), Reprendre (suspended to running), Annuler (any to cancelled, with confirmation), Remettre en brouillon (cancelled to draft). The status bar is `clickable`, so clicking a step performs a plain `write({'state': ...})` with the same effect as the buttons (tested). New configs start in draft, so creating a rule no longer starts auditing by surprise.

`_get_config` now filters on `state = 'running'`. The snapshot code filters the same way, so "audited entity" means "running configuration" everywhere.

**Migration** [../migrations/17.0.1.1.0/post-migration.py](../migrations/17.0.1.1.0/post-migration.py): a new `required` column with default `draft` would leave all pre-existing rules in draft and silently stop auditing after the upgrade. The script sets `state = 'running'` for every existing row (they were auditing under v1). Migration folders are named after the target version and run when the manifest version rises past the stored one.

### Validation

- `_check_included_users`: toggle off requires at least one included user (otherwise nobody is audited).
- `_check_dates_order`: end strictly after start.
- `_check_not_in_past(vals)`, called from `create` and `write`, **only for dates present in `vals` and different from the stored value**. So editing other fields of a running configuration whose start date is now in the past works. One minute of tolerance (`PAST_TOLERANCE`) because the datetime picker has minute precision: a "now" picked in the UI is already some seconds old when saved.
- `_check_model_allowed` and the SQL unique constraint on `model_id` are from v1.

### Caching (important concept)

`_get_config(model_name)` is wrapped in `@tools.ormcache('model_name')` because it runs on **every** create/write/unlink in the ERP. Consequences:

- `create`, `write`, `unlink` of a config call `self.env.registry.clear_cache()` **after** the change, so edits apply immediately (and across workers: Odoo signals other processes through the cache sequence).
- The cache therefore stores only things that change when a config is edited: flags, field set, user set, dates. It cannot store "does now fall inside the period" or "is this user allowed", because those depend on the clock and the caller. Those two checks stay in `_audit_config`. The dates are cached as data, the comparison is done live.
- The cached value is a plain dict of frozensets, not a record, so it is safe to share between environments.

### Chatter and tracking

`mail.thread` + `mail.activity.mixin`. Every business field has `tracking=True`, so each edit posts "old to new" in the chatter. Odoo 17 supports tracking on Many2many, so user lists are tracked too. `state` tracking gives a free history of Démarrer/Suspendre/Annuler.

## 4. Journal entry (`audit.log`)

[../models/audit_log.py](../models/audit_log.py)

Chatter on an **immutable** record needs three adjustments:

1. `_mail_post_access = 'read'`: by default posting a message requires *write* access to the record. Utilisateur group only has read, so without this nobody could leave a note.
2. `write()` still raises `UserError` ("Les journaux ne peuvent pas être modifiés") **unless** the keys are a subset of `{'message_main_attachment_id'}`. Odoo writes that technical field itself when someone attaches a file in the chatter; blocking it crashes the post. Anything else stays blocked.
3. Creation flags from section 2 so entries do not generate chatter noise.

`unlink()` still always raises. The purge is the only door (next section).

## 5. Purge

[../models/audit_purge.py](../models/audit_purge.py), [../views/audit_purge_views.xml](../views/audit_purge_views.xml), [ADR 0001](adr/0001-purge-of-audit-entries.en.md) ([FR](adr/0001-purge-des-entrees-daudit.fr.md))

### Decision

v1 promised "nobody can delete a log". That grows the table forever, and the only remedy is raw SQL, which is untraceable. The ADR replaces the promise with: **only a traced, administrator-only purge can delete entries.** Rejected options: permanent immutability; automatic retention (deletion without a human decision is harder to defend in an audit).

### Mechanism

1. Wizard (`audit.purge.wizard`, a `TransientModel`): cutoff datetime (default now minus 90 days), computed `entries_count` shown live, "Purger" button with a confirm dialog, hidden when count is 0.
2. `action_purge` re-checks the group **on the server**, refuses a future cutoff, then calls `audit.log._purge_before(cutoff)`.
3. `_purge_before` checks the group *again*, then deletes with **plain SQL**: first the `mail_message`, `mail_followers`, `mail_activity` rows hanging on the old entries, then `audit_log` rows. `audit_log_line` rows disappear through the `ondelete='cascade'` foreign key. It flushes first and invalidates all caches after, since raw SQL bypasses the ORM.
4. A trace record `audit.purge` is created with `sudo()`: who, when, cutoff, count.

Why SQL and not a flag in `unlink()`: the immutability guard stays unconditional and simple. The one bypass is one private method (leading underscore means it cannot be called over RPC from the browser), which is exactly what the ADR consequences require ("keep this path restricted").

Why the chatter rows are deleted by hand: `mail_message` is polymorphic (`model` + `res_id`), there is no foreign key, so cascade will not clean it and orphan messages would remain.

### Traces cannot hide a purge

`audit.purge` has the same write guard as `audit.log` (only `message_main_attachment_id` allowed), `unlink` always raises, it has a chatter, and the access CSV gives the admin group **read only**. Deleting evidence always leaves evidence.

### Defence in depth (a repeated pattern in v2)

Every admin-only feature is protected three times: menu hidden by `groups=`, access rights in `ir.model.access.csv`, and an explicit `has_group` check in Python. Tests assert the Python check separately ("wizard checks the group itself even with access"), because ACLs alone are easy to loosen by accident.

## 6. Snapshot ("Instance") and comparison

[../models/audit_snapshot.py](../models/audit_snapshot.py), [../views/audit_snapshot_views.xml](../views/audit_snapshot_views.xml)

Code says `snapshot`, UI says "Instance" (renamed during build; see CONTEXT.md).

### What is stored

Scope: entities with a **running** configuration at that moment, and **all** their fields (not only the tracked ones). Stored as three tables: `audit.snapshot` (name, date, user), `audit.snapshot.entity` (one row per entity), `audit.snapshot.field` (one row per field with `label, ttype, required, readonly, stored, relation, selection`). All values are text, normalised by `_text()` (False/None become empty string) so `True`/`False`/empty compare and display consistently.

The picture is taken inside `create()` via `_capture()`: saving the record is taking the snapshot. The form hides everything but the name until saved.

`_current_schema()` reads `ir.model.fields` with `sudo()` (audit admins are not system admins and cannot read that model) and `lang='en_US'` so two users with different languages never see a false "label changed" difference. Selection options are serialised as `value=label;...` ordered by `sequence`.

### Comparison

`_compute_diff()` is a pure function of (stored schema, current schema) and returns dicts. Kinds:

| kind | meaning |
| --- | --- |
| `entity_added` | running config now, not in snapshot |
| `entity_removed` | in snapshot, config no longer running, model still exists |
| `model_deleted` | in snapshot, model no longer in the registry (`model_name in self.env.registry` tells them apart) |
| `field_added`, `field_removed` | by field name |
| `field_changed` | one row per changed property, with old and new |

Two consumers: the dashboard (`audit.dashboard.compare`, returns rows as JSON) and `action_compare` (writes rows into the transient `audit.snapshot.diff` and opens a list, which gives filters, grouping and **Excel export for free** from the standard list view). Each user has one result per snapshot: a new click deletes the previous rows. The result is never stored permanently (transient models are vacuumed by Odoo's autovacuum).

### Size

`_compute_storage` sums `pg_column_size(row)` over the snapshot's entity and field rows with one grouped SQL query for all records in the recordset, then formats with `human_size`. It flushes the two models first so unsaved ORM writes are counted.

Snapshots are deletable by admins (they are not audit entries); children go by cascade.

## 7. Dashboard

[../models/audit_dashboard.py](../models/audit_dashboard.py), [../static/src/dashboard/](../static/src/dashboard/), [../views/audit_dashboard_views.xml](../views/audit_dashboard_views.xml)

### Architecture: hybrid

Community list/form/graph views cannot embed charts in a page next to KPI cards, so the page is an **OWL client action** (`ir.actions.client` with `tag="itc_audit_log.dashboard"`, registered in the `actions` registry). All numbers and rules stay in Python; JS only fetches and draws. The SPEC section 12 records this as a changed decision (earlier answer was "native").

- `audit.dashboard` is an `AbstractModel`: no table, only RPC methods `get_data(period)` and `compare(snapshot_id)`. Both start with `_check_admin()`. Hiding the menu is cosmetic; the server check is the real protection (tested).
- `get_data` returns: `rules_count`, `entries_count`, `size_bytes/size_label`, `top_users` (top 5), `per_day` (labels + values), `per_entity` (labels + values), `snapshots` (list for the selector).
- Periods: `7`, `30`, `90`, `all`; an unknown value falls back to 30 (so a tampered RPC argument cannot cause an error or an unbounded query).
- Aggregations are raw SQL `GROUP BY` after `flush_model()`, not `search` + Python loops, so cost stays flat as the journal grows.
- "per day" fills in days with zero entries so the axis is continuous; with period "all" it switches to per **month** (`date_trunc` + `to_char`), since years of daily bars are unreadable.
- Journal size is `pg_total_relation_size` of `audit_log` + `audit_log_line` (includes indexes and TOAST), independent of the period.
- Deleted users in the top list display "Utilisateur supprimé"; archived users resolve through `active_test=False`.

Front end ([../static/src/dashboard/audit_dashboard.js](../static/src/dashboard/audit_dashboard.js)):

- `loadJS("/web/static/lib/Chart/Chart.js")`: the Chart.js already bundled with Odoo, no CDN, works offline.
- Lifecycle hooks: `onWillStart` loads library + data; `onMounted`/`onPatched` call `drawCharts`; `onWillUnmount` destroys charts. Chart.js attaches to a canvas, so old chart objects must be `destroy()`ed before redrawing or they leak and flicker. `drawnFor === data` avoids redrawing on unrelated re-renders (e.g. choosing a snapshot in the select).
- Dates are formatted with `timeZone: 'UTC'` so a day label never shifts by timezone.
- Entity chart height grows with the number of entities (36 px per bar) instead of squashing labels.
- Buttons use the `action` service: journal, configuration, instances, and the purge wizard with `onClose: () => this.load()` so the KPIs refresh after a purge.
- A web tour ([../static/tests/tours/audit_dashboard_tour.js](../static/tests/tours/audit_dashboard_tour.js)) clicks through the page in a real browser; it is registered under `web.assets_tests`.

Assets are declared in the manifest under `web.assets_backend`. `/** @odoo-module **/` on the first line makes Odoo's bundler transpile the file into an ES module.

**Known mismatch:** the "Configurations" KPI counts non-archived configs (`search_count([])`), whatever their `state`. The SPEC says "active". Draft, suspended and cancelled configs are therefore counted although they audit nothing, and a test (`test_only_active_rules_are_counted`) locks in the archive-only behaviour. Decide which meaning you want; if "currently auditing", filter on `state = 'running'` and update the test.

## 8. Security

[../security/security.xml](../security/security.xml), [../security/ir.model.access.csv](../security/ir.model.access.csv)

Groups are unchanged: Utilisateur (read the journal and configuration) and Administrateur (implies Utilisateur; root and admin users added). The category name is "Model auditer".

| Model | Utilisateur | Administrateur |
| --- | --- | --- |
| audit.model.config | R | RWCD |
| audit.log, audit.log.line | R | R (inherited) |
| audit.purge | none | R |
| audit.snapshot (+ entity, field) | none | RWCD |
| audit.purge.wizard, audit.snapshot.diff | none | RWCD |

Transient models also need an ACL row in Odoo 17, which is why the wizard and diff models appear. `audit.log` has no write/create/unlink right for anyone: entries are created through `sudo()` in the hook. The purge-wizard window action also carries `groups_id`, and menus for Dashboard, Instances, Purge history and Configuration carry `groups="group_audit_admin"`. Note the Configuration menu is admin-only while the Utilisateur group still has a read ACL on `audit.model.config`; confirm that is intended (the security group comment still says Utilisateur can "consulter ... la configuration").

## 9. Menus

[../views/menus.xml](../views/menus.xml): root "Model auditer", then in order: Tableau de bord (admin), Journal des opérations, Instances (admin), Historique des purges (admin), Configuration (admin). The SPEC lists Configuration third; the build places it last.

## 10. Tests

All inherit `AuditCase` ([../tests/common.py](../tests/common.py)): `post_install`, a clean `res.partner` configuration set to `running`, helpers to create users and act as them. The shared case removes a pre-existing real configuration for partners inside the transaction (rolled back), so tests never depend on or alter real data.

| File | Covers |
| --- | --- |
| test_audit_log.py | v1 behaviour: create/write/unlink/archive, per-record entries, field filter, immutability, groups |
| test_audit_rule.py | user matching (included, excluded, OdooBot), period (before/inside/after/open), past-date validation, immediate effect |
| test_audit_state.py | lifecycle buttons, only `running` audits, status bar clicks, tracking, snapshot scope |
| test_audit_chatter.py | tracked changes, note on an entry, no message on creation, entry still immutable |
| test_audit_purge.py | only older entries, chatter removed, trace, future cutoff, non-admin, private method check |
| test_audit_snapshot.py | scope, size, every diff kind, transient result replaced, cascade delete, admin only |
| test_audit_dashboard.py | KPIs, period filter, top 5, chart data, fallback period, admin only, HttpCase tour |

Run: `odoo-bin -c odoo.conf -d <db> -u itc_audit_log --test-tags itc_audit_log --stop-after-init`.

## 11. Concept glossary

- **Abstract model / `_inherit = 'base'`**: a class with no table; inheriting `base` extends every model.
- **`ormcache` + `clear_cache`**: per-registry memoisation, invalidated explicitly on config edit.
- **`mail.thread`**: gives chatter, followers, tracking. `tracking=True` posts field changes. `mail_create_nolog` / `mail_notrack` / `mail_create_nosubscribe` are context flags that silence that behaviour.
- **`_mail_post_access`**: access level needed to post on a record (default write).
- **TransientModel**: temporary table cleaned by autovacuum; used for wizard and comparison result.
- **`sudo()` vs `with_user()`**: `sudo()` bypasses ACLs and record rules but keeps the uid, which is why the hook still sees the true acting user.
- **Client action / OWL**: a JS component registered under a tag and launched from `ir.actions.client`; it talks to Python through `orm.call`.
- **Raw SQL in Odoo**: needs `flush_model()` before (push pending ORM writes) and `invalidate_all()` after (drop stale caches).
- **Post-migration script**: runs after the module's data is loaded on version bump; here it fixes data created with a new column's default.
- **Web tour**: scripted browser test, run by `HttpCase.start_tour`.

## 12. Open points and stale artefacts found while comparing

1. **SPEC is behind the code.** It does not mention the `state` lifecycle, and names the date badge "En attente / En cours / Terminée" while the code uses "Pas commencée / Active / Terminée". Update SPEC sections 4 and 7 ("active configuration" now means `state = running`).
2. **Dashboard "Configurations" KPI** counts by archive flag, not by state (section 7).
3. **Form help text is stale** in [../views/audit_model_config_views.xml](../views/audit_model_config_views.xml): "Pour le mettre en pause, archivez cette configuration" predates the Suspendre button.
4. **`itc_audit_log.puml` is v1.** It lacks the user lists, dates, state, `model_label`, purge, snapshot and dashboard models.
5. **Old entries have no `model_label`** (no backfill in the migration). Cosmetic: the dashboard falls back to the technical name. A one-line `UPDATE` in the migration would fix it.
6. **Binary fields and bulk imports** remain the performance risks listed in DECISIONS "To discuss later". The purge now gives a manual answer for table growth; automatic retention is still undecided.
7. **`_compute_counts` and `_compute_storage` stacked decorators**: in [../models/audit_snapshot.py:57](../models/audit_snapshot.py#L57) the `@api.depends` for `_compute_storage` is separated from its `def` by blank lines and a comment. It works in Python but reads like a mistake; move the comment above the decorator.
