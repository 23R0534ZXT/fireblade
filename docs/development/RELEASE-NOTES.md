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
- Animation vectorielle de démarrage de **10 secondes**, avec braises, allumage progressif, flammes, fumée et transition vers le logo, désactivable dans les préférences d’organisation.

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
