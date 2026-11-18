# Les entrées d'audit peuvent être purgées, par les administrateurs uniquement, et chaque purge est tracée

Le module avait été spécifié pour que personne, administrateurs compris, ne puisse supprimer une entrée d'audit (« un journal qu'on peut effacer ne prouve rien »). Le journal grossit à chaque opération surveillée, nous autorisons donc maintenant une purge. Elle est réservée au groupe Administrateur, ne supprime que les entrées plus anciennes qu'une date limite choisie par l'administrateur, demande une confirmation finale et écrit toujours une trace de purge permanente (qui, quand, date limite, nombre d'entrées). Les entrées restent impossibles à modifier ou à supprimer par tout autre chemin.

## Options étudiées

- **Garder le journal définitivement immuable.** C'est le plus simple et la garantie la plus forte, mais la table grossit sans limite et le seul remède serait du SQL manuel, qui ne laisse aucune trace.
- **Rétention automatique (suppression après N jours).** Elle supprime des entrées sans que personne ne l'ait décidé, ce qui est plus difficile à défendre lors d'un audit.

## Conséquences

- La promesse n'est plus « personne ne peut supprimer d'entrées ». Elle devient « seule une purge tracée, réservée aux administrateurs, peut supprimer des entrées ».
- Les traces de purge ne peuvent pas être purgées elles-mêmes : supprimer des preuves laisse toujours une preuve.
- La purge nécessite un chemin de suppression dédié et privé qui contourne la protection d'immutabilité des entrées. Toute modification de cette protection doit conserver ce chemin fonctionnel et restreint.
