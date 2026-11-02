# Fireblade 0.7 — contrôle de couverture

Validation locale sous Linux, Python 3.12.14, DuckDB 1.5.6 et PySide6 6.12.0. La suite complète passe : **1 005 tests réussis, 28 ignorés**, en 168,22 secondes. Les tests Qt utilisent la plateforme `offscreen` ; ils ne qualifient pas l’EXE Windows.

Après les derniers ajustements, **64 contrôles ciblés**, puis **44 contrôles ciblés** passent sur les parcours touchés : audit, chronologie, journal persistant, erreurs, annulation, export, rapports, transport du case et aide intégrée. Les dernières vérifications couvrent aussi la modification des annotations après indexation et le budget réel des fichiers JSON indentés.

## Scénario reproductible

`python scripts/benchmarks/coverage.py` crée deux analyses totalisant **120 000 lignes**, avec dates zonées, dates sans fuseau, dates invalides, dates absentes, valeurs multilignes et une colonne vide. Le contrôle vérifie pour chaque analyse 60 000 lignes lues, 6 000 retenues par la vue, 30 000 dates exploitables, 30 000 sans date et 15 000 dates sans fuseau. Les SHA-256 des originaux restent identiques après lecture.

Deux mesures locales : **0,21–0,23 seconde** pour l’audit approfondi avec relecture des SHA-256 ; **0,06 seconde** pour exporter les 6 000 résultats filtrés et vérifier indépendamment le schéma, le nombre de lignes, les valeurs textuelles et le SHA-256 du CSV produit. Ces durées dépendent du matériel et des données. Elles ne prédisent pas les performances de grandes collectes réelles, des classeurs XLSX ou de lecteurs externes.

## Pannes et limites exercées

- Source modifiée à taille constante, source disparue, base indisponible et incohérence du nombre de lignes.
- Identifiants de lignes dupliqués, colonnes entièrement vides et vues filtrées sans résultat.
- Dates absentes ou invalides, exemples liés aux numéros de ligne et fuseaux non explicites.
- Lecteur en échec, avertissement de sortie partielle, sortie manquante, inventaire interrompu, famille attendue absente et fichier non inventorié.
- Analyses fermées, périmètre d’index ancien, annotations modifiées après indexation, dates masquées et chasse IOC aux détails limités.
- Relecture CSV et XLSX, cellules finales vides, comparaison des valeurs et export modifié après création.
- Un rédacteur XLSX volontairement défectueux écrit le bon nombre de lignes avec des valeurs incorrectes : la relecture refuse l’export et conserve la destination précédente.
- Un contrôle annulé conserve le bilan précédent ; un export interrompu avant remplacement conserve son ancienne destination.
- Journal ou bilan sauvegardé/rechargé, plan attendu conservé, journal endommagé préservé et protection des fichiers de contrôle contre les exports.
- Transport du journal et du dernier bilan avec réaffectation des références, sans réécriture des causes ou exemples sources.
- Lecture intégrale du guide dans l’application et fenêtre utilisable à **1024 × 600**.

Le contrôle décrit son périmètre et les vérifications désactivées. Les fichiers jamais acquis, hôtes absents et périodes de rétention attendues exigent un référentiel indépendant. Le journal est borné, les grands détails sont explicitement abrégés et les omissions de constats sont comptées. Les incidents historiques ne sont pas assimilés aux problèmes actuels.
