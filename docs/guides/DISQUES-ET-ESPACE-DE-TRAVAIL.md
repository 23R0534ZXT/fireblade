# Fireblade 0.2.0 — parcours case et analyse de disque

Ces fonctionnalités sont dans les sources en développement. Le téléchargement
Windows 0.1.1 publié ne les contient pas ; le [nouvel EXE Windows a passé ses qualifications](https://github.com/23R0534ZXT/fireblade/actions/runs/41673982489),
mais n’a pas encore été publié comme release. Il est disponible dans les artefacts
de cette exécution GitHub Actions.

## Commencer

L’application demande de créer ou d’ouvrir un **case** avant toute analyse.
Les enquêtes existantes restent réutilisables. Après création, deux choix sont
proposés dans Analyses :

- **Analyser un fichier de données** : parcours CSV, TSV, TXT, XLS et XLSX existant.
- **Analyser un disque logique ou un disque complet** : choix de la source, puis
  ouverture immédiate de l’espace de travail et traitement en arrière-plan.

Les imports de collectes, sessions et analyses existantes restent accessibles
par le menu Fichier une fois le case ouvert.

## Sources de disque

- **Volume monté** : choisir sa racine, ou un dossier de collecte contenant les
  répertoires des partitions et artefacts sauvegardés.
- **Image disque RAW / E01** : choisir le fichier image ; Dissect détecte les
  partitions et les systèmes de fichiers lisibles. Pour E01 segmenté, conserver
  les segments ensemble et sélectionner le premier.
- **Disque physique** : saisir son chemin de périphérique. Les droits et la
  lisibilité dépendent du système hôte. L’accès physique Windows et les images
  E01 n’ont pas encore été qualifiés par les tests locaux de ce changement.

Les lecteurs de fichiers intégrés à cette extension sont NTFS, FAT et ext.
Les volumes chiffrés ne sont pas déverrouillés ; un système de fichiers absent
ou illisible ne constitue pas une analyse réussie.

Le case doit être stocké hors du volume monté sélectionné. Pour un périphérique physique, Fireblade vérifie aussi que le case ne se trouve
pas sur le disque source ; si la localisation ne peut pas être déterminée,
l’analyse physique est refusée. Les sources sont
ouvertes en lecture seule. Fireblade n’effectue ni acquisition de disque, ni
récupération de fichiers supprimés, ni analyse de l’espace non alloué. Un volume
actif peut évoluer : préférer une acquisition hors ligne ou un support protégé
en écriture pour une investigation reproductible.

## Traitement progressif

Le travail parcourt les fichiers, sélectionne les candidats aux formats déjà
pris en charge (journaux, ruches, MFT, Prefetch, LNK, SQLite, etc.), copie ces
artefacts dans le case et invoque les lecteurs existants. Il ne copie pas tous
les fichiers du disque. La disponibilité des parseurs Windows dépend du pack
embarqué ; un parseur absent reste une erreur visible.

Chaque base d’analyse est fermée après écriture et les contrôles de la source
sont effectués avant publication de ses résultats. Les nouveaux onglets sont
ajoutés sans remplacer l’onglet consulté. Une analyse encore en cours n’est pas
consultable ligne par ligne ; les analyses déjà terminées le sont.

En bas à droite, l’indicateur affiche la découverte, le chemin copié ou le
parseur actif. La progression est indéterminée : le nombre total d’artefacts et
leur coût ne sont pas connus à l’avance. Le bouton **Arrêter** demande l’arrêt
et conserve les résultats déjà terminés. La fermeture de l’application et le
changement de case attendent la fin ou l’arrêt de cette tâche.

Un seul disque est traité à la fois. Les requêtes des grilles utilisent un autre
pool de travail. Les traitements partagent néanmoins le CPU, la mémoire et les
accès disque de la machine ; une grosse analyse peut réduire leur réactivité.

Le bilan de collecte conserve les erreurs, résultats non reconnus et chemins
sources. Les artefacts copiés ont un SHA-256 ; ce contrôle n’est pas une empreinte
complète de l’image disque. `disk-source.json` conserve aussi le relevé des
extractions. Les artefacts copiés restent dans la collecte et sont transportés
avec son archive portable ; l’image disque originale n’est pas incluse. Une annulation conserve la session des résultats produits ; elle
ne permet pas encore de reprendre le parcours au dernier fichier visité.

## Organiser l’espace de travail

Dans **Affichage → Organiser l’espace de travail** :

- choisir l’arbre **disque → partition → dossiers**, le regroupement par type
  d’artefact ou la liste des analyses par collecte ;
- placer l’arbre à gauche ou à droite, l’afficher ou le masquer ;
- afficher ou masquer les détails de ligne et les barres d’outils, placer les
  détails en bas, en haut ou à droite ;
- déplier ou replier l’arbre ;
- activer ou désactiver l’animation au prochain démarrage.

Les choix de regroupement, de côté et de visibilité sont enregistrés dans les
préférences utilisateur. Les séparateurs permettent de redimensionner les
panneaux. L’arbre représente les dossiers **contenant des analyses publiées**,
pas un explorateur exhaustif de tous les fichiers du disque.

## Validation locale

Tests automatisés sous Linux/Qt hors écran : volume de journaux, image FAT12
valide de test, disque RAW MBR à deux partitions, publication progressive, interrogation
pendant le traitement, annulation et conservation des résultats, réouverture du
case et restauration de l’arbre. Les tests de sources ont aussi passé sous Windows (Python 3.11/3.12/3.13),
puis l’EXE a passé les contrôles de programme autonome, d’affichage, de charge
supérieure à 3 Gio et de 320 analyses. [Exécution de référence](https://github.com/23R0534ZXT/fireblade/actions/runs/41673982489).
Ces tests ne qualifient pas NTFS, ext, E01, tous les disques physiques ni les
supports endommagés.
