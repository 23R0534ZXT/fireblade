# Fireblade 0.2.2 — espace d’analyse modulable

- Arbre des artefacts : choix direct famille / dossier / liste, familles reconnues et nombre d’analyses.
- Recherche globale par défaut dans les artefacts ouverts ; panneau de résultats, masquage des résultats vides et saut à la source.
- Panneaux détachables, ancrables et redimensionnables ; dispositions Analyse, Chronologie seule et côte à côte ; enregistrement local de la disposition.
- Ordre et largeur des colonnes mémorisés automatiquement par format après déplacement des en-têtes.
- Surlignage des occurrences uniquement ; prise en charge des caractères Unicode hors BMP.
- Chronologie agrandie, commandes compactes, périodes rapides et détection des colonnes Time / Horodatage ; construction à l’ouverture.
- Ressources persistantes : mémoire, threads de requête et threads d’import/parsing. Les collectes restent séquentielles ; les moteurs externes conservent leurs propres options.
- Création de règles ciblant une cellule depuis le clic droit. Règles accessibles depuis la barre d’espace de travail ; création de profils JSON personnalisés à partir de l’artefact courant ; accès aux lecteurs .NET.

# Fireblade 0.2.1 — imports progressifs, menus et intégrité

## Ajouter des données depuis Analyse

L’accueil du case et la grille proposent directement les trois entrées : fichier de données, dossier à parser et disque. Le menu **Case** gère les enquêtes et leurs sauvegardes ; **Analyse** réunit les données et les outils d’investigation ; **Détection** donne accès à Hayabusa et aux IOC ; **Exporter** rassemble les sorties. Les options d’affichage sont regroupées par colonnes, groupes, vues, couleurs et navigation.

Le bilan de parsing reste dans **Imports**. Le seuil et le lancement d’Hayabusa disposent d’un écran **Détection EVTX** distinct ; la chasse IOC conserve son propre espace. Les diagnostics se consultent à la demande dans **Aide → Vérifier les imports et diagnostics…**, sans onglet principal permanent.

## Dossiers traités en arrière-plan

- Sélection de plusieurs dossiers avec **Ctrl/Shift** dans le sélecteur. Ils sont traités successivement dans le même case ; Arrêter annule aussi les dossiers encore en attente.

- Les dossiers utilisent le même traitement de fond que les disques. Un seul import tourne à la fois ; la grille reste utilisable et le bouton Arrêter conserve les résultats terminés.
- Par défaut, chaque résultat fermé et vérifié apparaît progressivement, sans changer l’analyse déjà consultée.
- Les regroupements par artefact ou dans une grille unique restent disponibles ; leurs résultats apparaissent une fois le regroupement terminé.
- Les analyses ajoutées sont rattachées au case et retrouvent leur place à sa réouverture.

## Petites machines et démarrage

- Réglage par défaut : **un thread et 128 Mio par base DuckDB**. Le parsing de fond reçoit la moitié du budget configuré, avec un minimum de 64 Mio, et un thread.
- Les résultats sont intégrés par lots de seize ; les sauvegardes intermédiaires sont espacées et le minuteur de réception s’arrête au repos.
- Ces budgets ne plafonnent pas toute la RAM de Python, Qt ni des moteurs externes. La configuration utilisateur reste prioritaire.
- Animation de démarrage de **10 secondes** : feu réel sur fond sombre, allumage progressif et apparition du logo, désactivable dans les préférences d’organisation. La lecture reste locale et silencieuse, sans cache de toutes les images.

## Huit constats d’audit corrigés

- Parcours des vraies images NTFS sans l’erreur `is_junction` de l’adaptateur Dissect.
- Copie des compagnons SQLite WAL/SHM/journal ; rejet d’un groupe de fichiers changeant pendant sa copie.
- Analyses DuckDB reçues ouvertes sans accès SQL aux fichiers externes ; validation des objets stockés et refus des vues/métadonnées hostiles.
- Résultats d’une source dont l’intégrité a échoué retirés des sessions de collecte publiées.
- Mise à jour d’IDNA en **3.15** et contrôle précoce de longueur des domaines.
- Protection commune des exports : preuves brutes, compagnons, analyses, fichiers internes du case et alias par identité de fichier.
- Export des sources Hayabusa protégé et atomique, avec conservation de l’ancienne destination en cas d’échec.
- Sessions Fireblade/TLE et règles globales ne peuvent plus écraser les métadonnées du case.

## Validation et limites

La publication de l’EXE est conditionnée aux tests Windows Python 3.11/3.12/3.13, à la construction et à l’exécution autonome, aux lecteurs natifs, aux chemins UNC/longs, aux contrôles visuels, au scénario supérieur à 3 Gio et aux 320 analyses. L’empreinte de l’exécutable publié et son commit figurent à la fin de ces notes.

Les tests Linux comprennent les régressions d’audit, les trois organisations d’import de dossier, les requêtes pendant le parsing, la réouverture du case et les parcours de menus. Un essai de dossier de 250 000 lignes a aussi conservé la source et le traitement des événements Qt, avec les budgets DuckDB de 128/64 Mio ; ses mesures ne qualifient pas toutes les machines virtuelles.

Fireblade reste un prototype non signé. Les disques sont lus pour extraire les artefacts pris en charge : pas d’acquisition complète, de déchiffrement, de carving ni de récupération des fichiers supprimés. Les formats et périphériques non exercés ne sont pas qualifiés par ces résultats.

## Mémoire et stockage

- Si le lecteur CSV natif atteint son budget, l’import reprend dans une transaction neuve avec des lots de lignes liés par paramètres. Les pages larges sont lues par lots de colonnes. Le budget mémoire n’est pas augmenté automatiquement.
- **Cases → Archiver et libérer l’espace** crée une archive portable vérifiée, garde une référence dans le catalogue, puis retire les fichiers locaux. Les preuves externes restent intactes. La restauration se lance depuis le catalogue.
- Les bases fermées sont archivées directement après checkpoint, sans seconde copie intégrale sur le disque. Les fichiers complémentaires du case sont conservés dans l’archive.
- Le README est désormais en anglais et présente les capacités, les limites et les procédures de manière structurée.
