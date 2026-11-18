# itc_audit_log: decisions and things to discuss later

The v2 design (per-user and per-period audit, chatter, dashboard, purge, schema snapshot) is in [docs/SPEC.md](docs/SPEC.md). The vocabulary is in [CONTEXT.md](CONTEXT.md).

## Decided (v1, built)
- Edit that changes `active` and other fields in one write: two logs (one archive/unarchive, one write).
- One log per record, not per call (bulk edit of 50 records = 50 logs).
- No field is skipped, including binary fields (photo). Magic fields (id, create_*, write_*) are not detailed: the log already has user and date.
- Only stored fields and one2many are tracked (non-stored computed fields never change by themselves).
- Exception: password fields are masked (`********`), never stored.
- Models never audited: `audit.*` only (prevents an infinite loop).
- Create with "track only some fields": log only the chosen fields.
- Two roles, defined in `security/security.xml`: Admin (config + logs) and User (view only). Nobody can create/edit/delete logs through UI or standard ORM; the code writes logs with `sudo()`. Since v2, the only exception is the administrator purge ([ADR 0001](docs/adr/0001-purge-of-audit-entries.en.md)).
- UI and user guide in French. Spec criterion 5 is ignored (removed from the document by the responsible).

## Decided (v2, built)
- Dependencies become `base` and `mail` only (for the chatter). Both ship with every Odoo.
- One configuration per entity stays; naming unchanged.
- Dashboard is a JavaScript page over Python data (see SPEC section 12).
- A configuration has a lifecycle (Brouillon, En cours, Suspendu, Annulé) shown as a clickable status bar. Only "En cours" audits and only "En cours" entities go in an instance. New ones start as Brouillon; configurations that existed before are migrated to "En cours".
- "Instantané" is now called "Instance" everywhere in the interface (code names still say snapshot).
- The date-based badge was renamed "Période" (Pas commencée / Active / Terminée) so it is not mixed up with the state.

## To discuss later
- One log per record: check performance and readability on big bulk operations (imports of thousands of rows).
- Binary fields (photos) are logged in full: each change stores old + new image text, so the log table can grow fast. Revisit if the database gets heavy.
- Retention policy: the purge is manual. Decide later whether an automatic retention is wanted.
