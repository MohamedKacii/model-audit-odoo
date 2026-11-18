# Audit entries can be purged, by administrators only, and every purge is recorded

The module was first specified so that nobody, administrators included, could delete audit entries ("a log you can erase proves nothing"). The journal grows with every watched operation, so we now allow a purge. It is restricted to the Administrateur group, deletes only entries older than a cutoff the administrator chooses, asks for a final confirmation, and always writes a permanent purge trace (who, when, cutoff, number of entries). Entries stay impossible to edit or delete through any other path.

## Considered options

- **Keep the journal permanently immutable.** Simplest and strongest guarantee, but the table grows without limit and the only remedy would be manual SQL, which leaves no trace at all.
- **Automatic retention (delete after N days).** Removes entries without anyone deciding to, so it is harder to defend in an audit.

## Consequences

- The promise is no longer "nobody can delete entries". It is "only a traced, administrator-only purge can delete entries".
- Purge traces cannot themselves be purged, so deleting evidence always leaves evidence.
- The purge needs one dedicated, private deletion path that bypasses the immutability guard on entries. Any change to that guard must keep this path working and keep it restricted.
