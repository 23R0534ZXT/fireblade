# Préparation 0.2 — cases, disques et organisation

Date : 3 novembre 2026. Base Git : `b677791` (0.1.1). Changements locaux de
préparation 0.2, sans publication ni reconstruction de l’EXE Windows.

## Comportements ajoutés

- Case obligatoire dans l’application ; ouverture d’un case existant possible.
  Le mode sans case reste explicitement réservé aux contrôles de composants
  (`Window(require_case=False)`). Les tests et outils de qualification existants
  utilisent désormais explicitement ce mode lorsqu’ils testent une grille isolée.
- Choix fichier de données ou disque depuis le case vide.
- Lecture seule de dossiers/volumes montés, images et périphériques physiques.
  Les artefacts reconnus sont copiés, hachés et traités par les lecteurs existants.
- Pool distinct pour le disque ; publication de bases fermées après contrôle des
  sources ; conservation de l’onglet actif et des résultats déjà publiés.
- Progression indéterminée en bas à droite, détails du traitement et annulation.
  Changement de case et fermeture protégés tant que la tâche est active.
- Arbre disque/partition/dossiers, regroupement par famille ou liste ; côté,
  visibilité, détails et barres d’outils configurables, préférences persistantes.
- Animation vectorielle au démarrage, désactivable.
- Conservation des artefacts extraits et réécriture des références lors du
  transport d’un case portable.

## Contrôles exécutés

La dernière exécution de la suite complète a terminé avec **1 165 tests réussis
et 28 ignorés** sous Linux / Qt hors écran, en 299,31 secondes. Après les derniers
ajustements de restauration de visibilité et de refus d’une destination invalide,
**50 tests ciblés ont réussi** (interface, disques, archives portables, version et
publication). Ruff, `git diff --check`, `pip check`, la cohérence de version 0.2.0
et les liens locaux des documents modifiés ont également réussi.

Un lecteur disque autonome **PyInstaller onefile sous Linux** a été construit
avec les mêmes options de collecte Dissect que le build Windows, puis exécuté
sur l’image FAT12 : une partition et une analyse importée, résultat réussi.
[Empreinte et portée du contrôle](20261103-v02-freeze-smoke-linux.json).
Les dépendances disque avec les contraintes épinglées du runtime ont aussi été
résolues et téléchargées en roues Windows x64 pour Python 3.11, 3.12 et 3.13.
Cela ne constitue pas une exécution du nouvel EXE sous Windows.

Les nouveaux tests couvrent :

- volume contenant des journaux Linux ; absence de modification de la source ;
- image synthétique FAT12 valide et disque RAW MBR à deux partitions ;
- chemin de lecture de périphérique exercé avec un flux RAW de test sous Linux ;
- consultation d’une base pendant que la tâche disque reste active ;
- requête dans une grille pendant le traitement, sans blocage global ;
- refus de changer de case, annulation et résultats partiels ;
- refus d’un case stocké dans la source, avant toute écriture ;
- image invalide, réouverture du case, organisation et arbre restaurés ;
- export/import portable des copies et de leur provenance ;
- fin de l’animation avec traitement continu des événements Qt ;
- copie tronquée rejetée et sorties d’une source modifiée non publiées ;
- journaux de registre en minuscules copiés une seule fois ;
- fin d’indexation différée pendant une requête active ;
- échec de sauvegarde initiale sans lancement de tâche orpheline ;
- annulation avant démarrage avec bilan enregistré ;
- contrôle de localisation de la destination physique et refus avant création
  d’un dossier de travail dans la source ;
- restauration effective de la visibilité du panneau de détails.

Des captures de contrôle ont été rendues sous Qt hors écran pour l’accueil,
l’animation et l’espace de travail avec arbre et grille.

## Limites de la preuve

Aucune qualification native de cette extension sous Windows, aucun test de
périphérique physique réel, d’E01, de NTFS ou d’ext n’est attesté ici. Le code
Windows de lecture physique utilise une ouverture `rb` et la demande de longueur
`IOCTL_DISK_GET_LENGTH_INFO` ; cela reste à vérifier sur un poste approprié.
Les parseurs Windows dépendent du pack embarqué et leurs erreurs restent dans le
bilan. Ni acquisition, déchiffrement, carving ni récupération de fichiers
supprimés. Le parcours interrompu ne reprend pas encore au dernier fichier.

Les dépendances Dissect et flow.record ajoutées sont sous AGPL-3.0-or-later ;
les versions et notices sont déclarées dans le dépôt et la collecte de notices
pour la construction Windows a été étendue. Aucun nouvel EXE n’est publié.
