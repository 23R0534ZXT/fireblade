# Fireblade 0.2.0 — cases, disques et espace de travail

## Un case avant toute analyse

À l’ouverture, créez ou ouvrez un dossier d’enquête. Un nouveau case propose deux
parcours : analyser un fichier de données (CSV, TSV, TXT, XLS ou XLSX) ou analyser
un disque logique / disque complet. Les collectes, sessions et analyses existantes
restent disponibles dans le menu Fichier une fois le case ouvert.

## Analyse de disque en arrière-plan

- Sources : volumes montés et dossiers de collecte, images RAW / E01, chemins de
  périphériques physiques. Lecteurs de systèmes de fichiers : NTFS, FAT et ext.
- Lecture seule, copie des artefacts reconnus dans le case, empreintes SHA-256 et
  traitement par les lecteurs existants. Ce parcours ne copie pas tout le disque.
- Accès immédiat à l’espace de travail ; chaque analyse terminée devient
  consultable sans attendre la fin du disque ni remplacer l’onglet actif.
- Indicateur en bas à droite : découverte, extraction et parseur actif. Bouton
  d’arrêt avec conservation des résultats déjà produits.
- Case protégé contre le changement d’enquête et la fermeture pendant la tâche.
  Copies et références conservées dans les archives portables.

## Organisation et démarrage

- Arbre disque → partition → dossiers → analyses ; autres modes par famille
  d’artefact ou en liste.
- **Affichage → Organiser l’espace de travail** : côté et visibilité de l’arbre,
  position des détails, barres d’outils, déplier/replier, préférences sauvegardées.
- Animation vectorielle de démarrage, désactivable dans le même menu.

## Validation et disponibilité

Version de l’application et du binaire Windows : **0.2.0**. L’exécutable joint
à cette release est celui du commit qualifié `43893ab`, sans reconstruction.
Les anciens téléchargements 0.1.1 ne contiennent pas les nouveautés ci-dessus.

La [qualification Windows du correctif 0.2.0](https://github.com/23R0534ZXT/fireblade/actions/runs/41673982489) a réussi :
tests Python 3.11/3.12/3.13, EXE autonome, lecteurs, chemins UNC/longs, apparences,
charge supérieure à 3 Gio et parcours à 320 analyses. Le binaire publié provient de cette exécution ; son empreinte SHA-256 a été
comparée au rapport de vérification du programme autonome avant publication.

La validation Linux/Qt hors écran couvre notamment une image FAT12, un disque RAW
MBR à deux partitions, la publication progressive, les requêtes pendant la tâche,
l’annulation, la réouverture du case et les archives portables. Voir le
[rapport de développement](../validation/reports/20261103-v02-case-disk-linux.md).

Les accès physiques Windows, E01, NTFS et ext demandent encore une qualification
appropriée. Pas d’acquisition de disque, de déchiffrement, de carving ni de
récupération des fichiers supprimés ; pas de reprise du parcours au dernier
fichier après interruption. Les erreurs d’accès et parseurs manquants restent
visibles. Un volume actif peut changer pendant sa lecture.

[Guide et limites](../guides/DISQUES-ET-ESPACE-DE-TRAVAIL.md) ·
[Historique 0.1.1](../archive/RELEASE-NOTES-HISTORIQUE.md)
