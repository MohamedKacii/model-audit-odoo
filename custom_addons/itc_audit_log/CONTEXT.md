# ITC Audit Log

Tracks who created, changed, deleted or archived what in the ERP, for the entities an administrator chooses to watch. It exists so that every watched operation can be traced and proven afterwards.

## Language

**Entité**:
A kind of record in the ERP that can be watched (for example Étudiant or Contact).
_Avoid_: Module, table (shown as "modèle" in the dashboard charts)

**Règle**:
The setting that says how one entité is watched: which operations, which fields, which users, and when. There is one règle per entité, and it is edited in the Configuration menu.
_Avoid_: Config, paramétrage

**Utilisateur audité**:
A user whose actions are recorded under a règle. A règle either watches only a chosen set of users, or watches everyone except a chosen set.
_Avoid_: User concerné, user suivi

**Entrée d'audit**:
One row of the journal: a single operation performed by one user on one record.
_Avoid_: Log, trace, ligne de journal

**Journal**:
The whole collection of entrées d'audit.
_Avoid_: Logs, historique

**Détail**:
One changed field inside an entrée d'audit, with its old and new value.
_Avoid_: Ligne, line

**Période d'audit**:
The date-and-time window during which a règle is in force. Outside it, the règle is ignored.
_Avoid_: Planning, schedule

**Purge**:
The administrator-only deletion of entrées d'audit older than a chosen date. Every purge leaves a permanent trace.
_Avoid_: Nettoyage, suppression du journal

**Instance**:
A saved picture of the structure (entités and their fields) of the entités that have a règle, at one moment.
_Avoid_: Instantané, snapshot, sauvegarde

**Comparaison**:
The list of differences between the current structure of the audited entités and an instance.
_Avoid_: Diff
