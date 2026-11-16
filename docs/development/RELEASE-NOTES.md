# Fireblade 0.4.0 — lire ce que la collecte n'avait pas reconnu

## Bilan d'import : agir sur place

- Un fichier non reconnu, en erreur ou écarté reste dans le bilan avec sa ligne, son motif et son empreinte, et l'analyste peut agir dessus sans quitter Fireblade.
- **Voir le fichier** : aperçu texte, repli cp1252 quand le fichier n'est pas en UTF-8, affichage hexadécimal pour un binaire. Un fichier illisible affiche un message, jamais une erreur.
- **Copier les non traités…** : copie des fichiers sans analyse dans un dossier choisi, arborescence conservée, **copie et jamais déplacement** ; la preuve reste où elle a été saisie.
- **Exporter la liste…** : CSV UTF-8 de ce que le tableau affiche, filtres compris.
- **Écarter du bilan** / **Réintégrer** : décision réversible, persistée avec la collecte, et sortie des compteurs de travail.
- **Supprimer…** : refusée si l'empreinte SHA-256 ne correspond plus à celle relevée à la collecte ; la suppression est tracée dans le bilan.
- Colonne **Motif** en clair, compteurs incluant les écartés, décisions enregistrées dans `collection.json`.

## Relancer un fichier avec le lecteur de son choix

- **Relancer avec un lecteur…** analyse le fichier sélectionné avec le lecteur choisi, l'importe comme n'importe quelle source et ouvre l'analyse obtenue.
- Quatre lecteurs : **texte** (une ligne par ligne), **page HTML enregistrée** (texte visible et liens, sans navigateur ni dépendance), **PDF (couche texte)**, **tableau CSV/TSV**.
- Le fichier n'est que lu, jamais modifié. L'empreinte relevée à la lecture devient la référence : une lecture ultérieure est refusée si le fichier a changé. Un fichier absent de la collecte ajoute sa ligne au bilan au lieu d'être refusé.
- Un binaire n'est jamais lu comme du texte, et un fichier sans ligne lisible dit pourquoi au lieu de produire une analyse vide.

## Fenêtre de collecte : deux questions, pas trois

L'écran qui s'ouvre avant un parsing proposait trois choix mélangés : « résultats
progressifs », « par artefact » et « vue unifiée ». Les deux premiers ne répondaient pas à
la même question, et le choix recommandé était le moins explicite.

Il pose maintenant les deux questions séparément, en anglais comme le reste de
l'interface : une case **« Keep working while the folder is parsed »** — on continue à
travailler pendant que le dossier est lu, chaque fichier analysé s'ouvrant dans sa propre
grille — puis le **résultat**, avec **« By artifact — recommended »** (un onglet par famille
d'artefact, tous listés dans l'arbre de navigation, chaque grille gardant ses colonnes) et
**« Unified view »** (une seule grille, groupée par artefact, groupement fixe).

Une vue fusionnée a besoin du dossier entier : le choix de disposition est donc grisé tant
que la case est cochée, avec la raison écrite dessous.

## Espace de travail : les mêmes barres dans tous les modes

- **Chronologie seule** ne cache plus que les panneaux détachables. Les barres du haut et
  la barre d'onglets (Analyses, Imports, Cases, Chronologie, IOC, EVTX) restent en place :
  c'était le chemin du retour, et il disparaissait avec le mode.
- Choisir un autre onglet sort du mode, au lieu de laisser la fenêtre à moitié déshabillée.
- **Analyse** rattache une chronologie détachée par « Analyse + chronologie » : les modes
  ne se mélangent plus.
- Sortir d'un mode ne casse plus si un panneau a été supprimé entre-temps ; « Rétablir les
  panneaux » remet aussi la barre d'onglets.
- Le badge du case, en haut à droite, respire : 12 px à gauche, 24 à droite, aligné à
  droite, pour qu'un nom long ne touche plus le bord de la fenêtre.

## Générique de démarrage : redessiné

- L'ancien générique collait une vidéo 320×426 dans la moitié droite et masquait ses
  coutures par des dégradés : mou, pixelisé, plus lourd que l'application qu'il annonce.
- Le nouveau est entièrement dessiné : mot centré sur un axe, nappe de lumière chaude,
  filet ambre, signature, version, ligne de progression et poussière qui dérive —
  déterministe, identique à chaque lancement.
- Il dure 6,5 s au lieu de 10 : de quoi respirer sans retenir le lancement.
- Quatre tests le regardent comme le ferait un œil : la fenêtre s'éclaire, les pixels
  allumés sont équilibrés autour du centre, le dernier cadre revient au noir, et la durée
  reste bornée.

## PDF : la couche texte, et rien d'autre

- Texte extrait page par page via `pypdf`, dans la même forme que les autres sources : une ligne par ligne, avec le numéro de page ; l'horodatage n'est retenu que s'il ouvre la ligne.
- **Pas d'OCR**, décision assumée : un PDF sans couche texte est signalé « PDF sans couche texte » et compté avec les avertissements, au lieu de produire des lignes vides qui ressembleraient à une analyse de la page.
- Une page abîmée n'emporte pas ses voisines : le numéro de page est noté, la lecture continue.
- Sans `pypdf`, Fireblade démarre normalement, le lecteur PDF est grisé dans la fenêtre de choix avec le motif. L'extension est épinglée dans `requirements/runtime.txt`, donc présente dans l'exécutable publié.

## Porte de vérification

- La suite tourne en **UTF-8** : les fixtures écrivaient leurs CSV sans `encoding=`, donc dans la page de code locale, alors que le code lit en UTF-8 et que la CI est en UTF-8. C'était 25 échecs sur 25 sans rapport avec le produit.
- Un dossier `%TEMP%\pytest-of-…` laissé par une exécution antérieure est purgé : Windows réutilisait l'ancien dossier sans corriger son orthographe, `resolve()` renvoyait la casse du disque et les chemins différaient d'une majuscule. C'étaient les 7 échecs restants.
- Le test qui vérifie que le cœur ne charge pas Qt garde désormais les paquets de l'interpréteur au lieu de les perdre en remplaçant `PYTHONPATH` : il échouait sur un détail d'environnement, pas sur une fuite de Qt.

## Ce que la lecture doit accepter

Un fichier texte n'arrive pas toujours en UTF-8 propre. Trois familles ont été trouvées en sondant de
vrais fichiers, et chacune était lue de travers :

- **UTF-16 avec BOM** — une sortie PowerShell redirigée, un fichier enregistré « Unicode » par Notepad :
  le fichier était refusé comme binaire, ou affiché avec un caractère NUL entre chaque lettre.
- **BOM UTF-8** — le caractère invisible restait en tête de la première ligne et empêchait la date
  d'être lue quand elle ouvrait le fichier.
- **Page HTML en cp1252** — enregistrée sur une machine française, elle perdait ses accents.

Le lecteur suit désormais l'ordre : encodage demandé, BOM, charset déclaré par la page, UTF-8, cp1252.
Et un fichier plus gros que la limite lue le dit (nombre de lignes et d'octets) au lieu de produire une
analyse qui paraît complète.

## Vérification

- Suite complète : **1 395 passés, 28 ignorés**, plateforme Qt Windows, fenêtre réelle construite, ruff propre.
- Sondes sur fichiers réels : 46 contrôles sur texte, page HTML, PDF (dont un de trois pages et un
  chiffré) et arborescence de collecte — 46 sur 46 ; journal de 100 000 lignes importé en 1,5 s.
- Aucun échec restant. Les familles d'échecs rencontrées venaient de la porte et de son garde-fou de
  fenêtres modales, jamais du produit.

# Fireblade 0.3.1 — toute l'interface en anglais et en français

## Langue

- L'interface est traduite **en entier**, et plus seulement les menus et les barres d'outils : fenêtres de dialogue, gestionnaire de colonnes, préférences, chasse IOC, couverture, chronologie, en-têtes de tableaux, listes déroulantes, infobulles, textes de saisie et messages d'état.
- Les **en-têtes de modèles** (tableaux de couverture, règles, chasse IOC, résultats), les **nœuds d'arbre** de la navigation, les **cellules** de tableau et les **noms de thèmes** sont traduits eux aussi : ce ne sont pas des widgets, ils ont leur propre passage.
- Les **guides intégrés** (tutoriel complet, guide d'utilisation, chronologie et sauvegardes, chasse IOC, couverture) existent en anglais et s'ouvrent selon la langue choisie, ainsi que les titres des fenêtres d'aide.
- **Cartes de condition et filtre ET / OU / NON** : opérateurs (« Contient », « Commence par », « Nombre ≥ », « Date égale »…), connecteurs, boutons (« Toutes les conditions », « Au moins une », « + Condition », « Replier/Déplier ») et la phrase de lecture du filtre sont traduits.
- **Notes de la sélection** : sur une sélection de lignes, le menu propose « Ajouter une note à la sélection… » tant qu'aucune n'en porte, puis « Éditer la note de la sélection… ». La fenêtre s'ouvre pré-remplie quand toutes les lignes partagent la même note, et le remplacement est explicite.
- **Notes de cellule** : un clic droit sur une valeur propose « Ajouter une note à la cellule… », puis « Éditer la note de la cellule… » une fois la note écrite. La cellule prend un fond vert, la note se relit dans la fenêtre et dans l'infobulle. Une note de ligne (signet) et des notes de cellule cohabitent ; retirer le signet ne supprime pas les notes de cellule. Les analyses ouvertes avant cette version sont migrées à l'ouverture, sans perte.
- **Double-clic sur une cellule** : il affiche la valeur en texte, JSON ou XML (choix dans la fenêtre), au lieu d'ouvrir l'éditeur de note. Le signet et sa note restent accessibles par le menu Édition et par un clic dans la première colonne. Les boutons des fenêtres de règles de coloration et de tri (« Ajouter », « Supprimer », « Monter », « Descendre ») sont traduits.
- Un **menu ouvert en popup** est désormais traduit : son arbre n'était jamais parcouru.
- Les messages **assemblés par concaténation** (`"Lecture du filtre : " + valeur`) sont traités comme des gabarits : le texte fixe et la valeur sont traduits séparément, puis recomposés.
- **Les textes calculés à l'affichage** passent par la même table : compteurs (« 2 case(s) affiché(s) »), fins de tâche, erreurs affichées, message d'archive vérifiée. La table accepte des gabarits (`Analyse absente : {}`) dont les valeurs sont réinsérées au moment de l'affichage, et l'entrée la plus précise l'emporte toujours.
- La traduction s'applique **à l'ouverture de chaque fenêtre** et **au moment où le code écrit le texte** : une liste remplie après coup, un compteur rafraîchi ou une erreur tardive sont couverts, sans toucher au code de chaque fenêtre.
- Le **français reste complet** : les libellés d'origine sont mémorisés par la couche de langue, et le retour au français se fait sans perte, y compris quand un texte avait été remplacé entre-temps.
- **À partir de la 0.3.2, on ne travaille plus que l'anglais** : les nouveaux libellés s'écrivent directement en anglais et le français déjà traduit n'est plus maintenu (il reste affichable, sans garantie de suivi).
- Six chaînes restent volontairement telles quelles : des noms de fichiers d'exemple (`évidence.csv`, `résumés.csv`, `fonctions étendues.csv`) et deux expressions TLE synthétiques. Ce sont des données, pas de l'interface.

## Corrections

- Un titre d'onglet n'accumule plus les esperluettes d'échappement d'un changement de langue à l'autre : `Chronologie & corrélations` finissait par s'afficher `Timeline &&&& correlations`.
- Un passage de langue ne réécrit plus les titres d'onglets quand le texte n'a pas changé, ce qui provoquait un ralentissement net sur un espace de travail chargé.

## Vérification

- Couverture mesurée : `scripts/i18n_inventory.py` liste toute chaîne française capable d'atteindre un écran. **946 sur 954 sont traduites**, les huit restantes sont des données.
- Deux tests de garde : une nouvelle chaîne non traduite fait échouer la suite, et la liste des reliquats ne peut que diminuer.
- Un test construit la vraie fenêtre en anglais et vérifie qu'aucun mot français n'y reste visible.
- Un balayage de la fenêtre réelle et de onze fenêtres de dialogue en anglais ne trouve **plus aucun texte français**.
- Suite complète : **1 327 tests passés**, 31 ignorés, aucune erreur, plateforme Qt Windows.

# Fireblade 0.3.0 — interface anglaise, regroupement et chronologie lisible

## Langue

- L’interface s’ouvre **en anglais** ; le **français** reste disponible dans **Préférences → Langue**. Le choix est enregistré.
- La traduction couvre les menus, les barres d’outils, les onglets, les boutons, les en-têtes, les filtres et les textes de saisie. Les textes calculés à l’affichage (compteurs, « aucun case actif ») restent en français pour l’instant.
- Un libellé non traduit s’affiche tel quel, jamais vide ni remplacé par une clé technique.

## Organisation de l’analyse

- **Barre de regroupement** repensée : niveaux numérotés, dépôt d’un en-tête à la position exacte, un `×` par niveau, et un bouton **Tout supprimer**.
- **Gestionnaire de colonnes** en deux volets : colonnes masquées à gauche, ordre à droite, plus la largeur et l’épinglage de la colonne choisie. L’ensemble est mémorisé par format d’artefact.
- **Palette de commandes** (`Ctrl+Shift+K`) : toutes les entrées de menus derrière un champ, y compris celles qui n’ont pas de bouton.

## Recherche

- La recherche inter-artefacts affiche désormais **les événements trouvés** — quatre lignes réelles sous le tableau — et le reste du volume, au lieu d’un simple compteur par fichier.

## Chronologie

- Les barres portent le **volume** : leur hauteur traduit le nombre d’événements de la tranche horaire.
- Les **pistes remplissent la hauteur** disponible au lieu de flotter dans un bandeau, et l’étiquette de la source est centrée.
- La barre d’actions reste visible en mode **Chronologie seule**.

## Corrections

- **Fenêtre vide au lancement** : la disposition enregistrée rejouait le mode chronologie avant qu’un case existe, masquant onglets et barres. Ce mode n’est plus rejoué au démarrage.
- **Barre « Parser un dossier »** : elle restait masquée jusqu’à un passage par Workspace → Analyse ; elle est visible et utilisable dès l’écran de lancement.
- **Fantôme après un glisser** : le regroupement s’applique après la fin du glisser, et l’en-tête reçoit le relâchement du bouton ; plus de colonne grisée qui reste affichée.
- **Bouton Ouvrir** : un changement de case refusé affiche maintenant sa raison au lieu de ne rien faire.
- **Onglets** : un `&` dans un titre ne s’affiche plus comme un souligné.
- La version est affichée en bas à droite de la barre d’état et de l’écran de lancement.

## Vérification

- Suite complète : **1 287 tests passés**, 31 ignorés, aucune erreur, plateforme Qt Windows.
- La suite ne peut plus se figer sur une fenêtre modale : un garde-fou rejette toute boîte laissée ouverte et la nomme.

# Fireblade 0.2.3 — chronologie fiable et récupération

- **Colonne de date** : une colonne UTC explicite (`Horodatage UTC`, `TimestampUtc`) l’emporte désormais sur la colonne brute dont elle est issue. Les journaux Linux, dont l’horodatage syslog n’a ni année ni fuseau, ne sont plus indexés sur la mauvaise colonne.
- **Fuseau de l’index** : les dates sans fuseau sont lues comme **UTC** dans la chronologie, comme à l’import. Le même dossier produit donc le même ordre chronologique d’un poste à l’autre ; seuls les modèles de test ou les réglages d’horloge ne peuvent plus le déplacer.
- **Colonnes calculées** : la date proposée est résolue contre le schéma réel de l’analyse, colonnes dérivées comprises. Une colonne UTC calculée est donc utilisable automatiquement, et un index deviné n’est plus mémorisé comme un choix : les réglages de chronologie enregistrés par la 0.2.2 sont réinitialisés une fois.
- **Dates de profil** : une déclaration `VisitTime` reconnaît un export `Visit Time`. Les analyses concernées n’ouvrent plus sans colonne temporelle.
- **Date et heure séparées** : un export qui écrit `date` et `time` dans deux colonnes (IIS, W3C, certaines timelines) est désormais indexé sur les deux colonnes combinées, et non sur la date seule à minuit. Le choix reste modifiable dans **Sources et dates…**.
- **Détection d’artefact** : le profil le plus spécifique l’emporte sur un profil plus étroit qu’il englobe. 18 entrées du catalogue — dont `HayabusaVerbose`, `HayabusaSuperVerbose`, `ChainsawPersistence` et neuf profils RECmd — n’étaient jamais sélectionnées et le sont maintenant. Une déclaration enregistrée sur une seule ligne tabulée (`MsftMft`) est découpée en colonnes.
- **Règles de profil** : les couleurs de catégories ne remplacent plus les règles du profil. Les seuils de sévérité Hayabusa retrouvent leurs couleurs.
- **Export interrompu** : une interruption pendant la vérification retire le fichier temporaire. Un nouvel export vers la même cible n’est plus refusé définitivement.
- **Robustesse** : un chemin de groupe plus profond que les regroupements de la vue produit un message explicite, et une ligne vide terminale d’un CSV de parseur n’annule plus tout le fichier.

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
