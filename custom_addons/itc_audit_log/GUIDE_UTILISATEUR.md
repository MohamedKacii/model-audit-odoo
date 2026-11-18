# Guide utilisateur : ITC Audit Log

Ce module enregistre automatiquement ce que font les utilisateurs sur les entités que vous choisissez : qui a créé, modifié, supprimé ou archivé quoi, et quand. Pour chaque modification, l'ancienne et la nouvelle valeur sont conservées.

Il ne demande que les modules `base` et `mail` (le chatter), présents dans toute installation d'Odoo.

## 1. Les deux profils

Les droits se gèrent dans Paramètres > Utilisateurs, rubrique **Model auditer**.

| | Utilisateur | Administrateur |
|---|---|---|
| Consulter le journal et laisser une note sur une entrée | oui | oui |
| Voir la configuration | oui | oui |
| Créer, modifier, archiver une configuration | non | oui |
| Tableau de bord | non | oui |
| Instances et comparaison | non | oui |
| Purger le journal et voir l'historique des purges | non | oui |

Personne ne peut modifier ou supprimer une entrée du journal, ni depuis l'interface ni par le code standard d'Odoo. C'est voulu : un journal qu'on peut effacer ne prouve rien. La seule exception est la purge décrite au point 6, réservée aux administrateurs et toujours tracée.

## 2. Choisir ce qu'on surveille

Menu **Model auditer > Configuration** (administrateurs), puis **Nouveau**. Il y a une configuration par entité.

1. **Modèle** : l'entité à surveiller (Contact, Étudiant, Résultat d'examen...). Les entités du journal lui-même ne sont pas proposées, sinon le module se journaliserait en boucle.
2. **Opérations à journaliser** : création, modification, suppression, archivage / désarchivage.
3. **Champs suivis** : « Suivre tous les champs » pour tout journaliser, ou décochez-le et choisissez les champs voulus.
4. **Utilisateurs audités** :
   - « Auditer tous les utilisateurs » coché : tout le monde est audité, sauf les utilisateurs listés dans « Sauf ces utilisateurs ».
   - Décoché : seuls les utilisateurs listés dans « Utilisateurs audités » sont audités. La liste ne peut pas être vide.
   - Les actions faites par le système (tâches planifiées, OdooBot) sont journalisées sous le nom d'OdooBot, sauf si vous l'ajoutez à la liste des exclus. Les utilisateurs archivés, comme OdooBot, sont bien proposés dans la liste.
5. **Période d'audit** : une date et heure de début et/ou de fin.
   - Sans date, l'audit est permanent. Avec un début seul : à partir de ce moment. Avec une fin seule : jusqu'à ce moment.
   - Cela permet de planifier un audit à l'avance, par exemple pour un week-end.
   - Les dates ne peuvent pas être dans le passé quand vous les saisissez ou les changez, et la fin doit venir après le début. Modifier une autre option d'une configuration déjà en cours reste possible.
   - Le badge **Pas commencée / Active / Terminée** indique où en est la période.
6. **État** : la barre en haut de la fiche (cliquable) suit la vie de la configuration.
   - **Brouillon** : une nouvelle configuration commence ici et ne journalise rien.
   - **En cours** : seul cet état audite. Bouton **Démarrer** (depuis Brouillon) ou **Reprendre** (depuis Suspendu).
   - **Suspendu** : pause temporaire, bouton **Suspendre**.
   - **Annulé** : bouton **Annuler** (avec confirmation) ; **Remettre en brouillon** pour repartir.
   - Vous pouvez aussi cliquer directement sur une étape de la barre. Chaque changement d'état est tracé dans le chatter.
7. **Période** : le badge à côté des dates dit si la période n'a pas commencé, est active ou est terminée. Une configuration n'audite que si son état est « En cours » **et** si la période est active.
8. **Archiver** la configuration (menu engrenage) la sort de la liste sans perdre le réglage.

Un changement de configuration s'applique tout de suite, sans redémarrage. Il n'y a qu'une période et qu'une liste d'utilisateurs à la fois par entité : pour auditer un deuxième week-end, modifiez les dates.

Chaque modification d'une configuration apparaît dans son **chatter** (en bas de la fiche) : qui a changé quoi, de quelle valeur à quelle valeur. Vous pouvez aussi y écrire un message, une note ou planifier une activité.

## 3. Lire le journal

Menu **Model auditer > Journal des opérations**. Chaque ligne est une entrée d'audit : une opération sur un enregistrement.

- **Création** : la fiche détaille les valeurs de départ (les champs vides sont ignorés).
- **Modification** : seuls les champs réellement modifiés apparaissent, avec l'ancienne et la nouvelle valeur. Réécrire la même valeur ne crée rien.
- **Suppression** : la fiche garde les valeurs que l'enregistrement avait juste avant d'être supprimé. L'entrée reste même si l'enregistrement a disparu.
- **Archivage / Désarchivage** : une ligne indique le passage de Vrai à Faux (ou l'inverse) du champ « actif ».

Si une même écriture archive un enregistrement et modifie d'autres champs, il y a deux entrées : une d'archivage, une de modification. Une modification en masse (50 enregistrements) donne 50 entrées, une par enregistrement.

Une entrée ne peut pas être modifiée, mais son **chatter** permet d'y laisser une note (« vérifié, rien d'anormal »).

### Chercher, filtrer, exporter

- Dans la barre de recherche : un utilisateur, une entité, un nom d'enregistrement ; les filtres Créations, Modifications, Suppressions, Archivages ; le filtre **Date** (mois, trimestre, année) ; le regroupement par utilisateur, entité, opération ou jour.
- Les vues **Graphique** et **Pivot** (boutons en haut à droite) donnent les opérations par jour et par utilisateur.
- Pour exporter vers Excel : cochez les lignes (ou la case en tête de colonne après avoir filtré), puis **Actions > Exporter**.

## 4. Tableau de bord

Menu **Model auditer > Tableau de bord** (administrateurs). C'est la première page du menu.

- **Sélecteur de période** : 7, 30 ou 90 derniers jours, ou tout. Par défaut 30 jours.
- **Configurations** : le nombre de configurations non archivées (indépendant de la période).
- **Opérations** : le nombre d'opérations journalisées sur la période.
- **Taille du journal** : la place réellement occupée sur le disque par le journal et ses détails (indépendante de la période).
- **Top des utilisateurs audités** : les cinq utilisateurs qui ont fait le plus d'opérations journalisées sur la période.
- **Deux graphiques** : les opérations par jour (par mois pour « Tout »), et les opérations par modèle.
- **Boutons** : voir le journal, aller à la configuration, purger les logs.
- **Comparaison de structure** : voir le point 7.

## 5. Les mots de passe, les photos et les champs système

- Les **photos et autres fichiers** sont journalisés comme les autres champs. Chaque changement stocke l'ancien et le nouveau contenu : surveiller des entités avec beaucoup d'images fait grossir la base.
- Les **mots de passe** sont la seule exception : leur valeur n'est jamais enregistrée, le journal affiche `********`.
- Les **champs système** (identifiant, créé par, créé le, modifié par, modifié le) ne sont pas détaillés : l'utilisateur et la date sont déjà sur chaque entrée.
- Les **champs calculés non enregistrés** en base ne sont pas suivis, puisqu'ils ne changent pas par eux-mêmes.
- Les imports, les modifications en masse et les appels API passent par le même chemin que l'interface : tout est journalisé de la même façon.
- Dans un script, `audit_skip=True` dans le contexte désactive la journalisation.

## 6. Purger le journal

Le journal grossit à chaque opération. Une purge supprime les entrées anciennes. Elle est réservée aux administrateurs (voir la décision dans `docs/adr/`).

1. Depuis le tableau de bord (bouton **Purger les logs**) ou depuis **Model auditer > Historique des purges**.
2. Choisissez la date limite : les entrées **plus anciennes** seront supprimées, avec leurs détails et leurs notes. Elle ne peut pas être dans le futur.
3. Le nombre d'entrées concernées s'affiche avant de valider, puis une confirmation est demandée. L'action est irréversible.
4. Une **trace de purge** est conservée pour toujours : qui, quand, jusqu'à quelle date, combien d'entrées. Elle ne peut ni être modifiée ni être supprimée, et son chatter permet de la commenter.

## 7. Instances et comparaison de la structure

Une instance garde la structure (les entités et tous leurs champs : type, libellé, obligatoire, lecture seule, stocké ou non, modèle lié, options de sélection) des entités dont la configuration est « En cours » à ce moment-là. Plus tard, la comparaison montre ce qui a changé : utile après une mise à jour pour voir quels champs ou entités ont bougé.

- **Prendre une instance** : menu **Model auditer > Instances > Nouveau**, donnez un nom, enregistrez. L'instance est prise à l'enregistrement. Sa fiche indique le nombre d'entités et de champs, et **la place qu'il occupe** dans la base.
- **Comparer** : bouton « Comparer à l'état actuel » sur la fiche d'une instance, ou panneau de comparaison du tableau de bord.
- **Résultat** : entité ajoutée ou retirée de l'audit, modèle supprimé d'Odoo, champ ajouté, champ supprimé, champ modifié (avec la propriété, l'avant et le maintenant). Le résultat s'affiche à la demande, il n'est pas conservé. Depuis le tableau de bord, « Ouvrir en liste » permet de filtrer et d'exporter vers Excel.
- Les instances peuvent être supprimées par les administrateurs : ce ne sont pas des entrées d'audit.

## 8. Pour les développeurs

Le module surcharge `create`, `write` et `unlink` une seule fois, sur le modèle abstrait `base`, donc aucun modèle n'a besoin d'être modifié. Le tableau de bord est une page OWL qui dessine les graphiques avec le Chart.js déjà fourni par Odoo ; tous les chiffres et toutes les règles restent en Python (`models/audit_dashboard.py`).

Les tests se lancent avec :

```
odoo-bin -d <base> -u itc_audit_log --test-enable --test-tags /itc_audit_log,-audit_tour --stop-after-init
```

Le test `audit_tour` ouvre le vrai tableau de bord dans Chrome sans écran ; il demande un serveur HTTP (retirez `--no-http`) et un navigateur Chrome installé.
