# Qualification de la collecte fournie et des grilles Host

Cette passe prolonge [la recette précédente](CONTINUED.md) sur
`codex/host-gui-review`. Le travail est préparé pour la version 0.10.0 ; sa publication sur GitHub a été
autorisée à la fin de la recette. Aucune fusion dans `main` n’est effectuée. Les données, captures et exports de la collecte privée restent hors
du repository, dans `/workspace/shared/downloads/kagarasu-real-collection/`.

## Résultats sur la collecte réelle

L'archive fournie contient 2 674 fichiers, dont 177 EVTX, des ruches de registre,
des bases SQLite et leurs compagnons, des fichiers Prefetch, une MFT, des raccourcis,
des exports tabulaires et de nombreux documents de configuration. Elle représente
986 541 590 octets compressés et 3 145 214 044 octets décompressés.

L'import final, réalisé depuis le dialogue graphique du conteneur, produit
**1 386 061 lignes et 1 478 analyses sources**. Sa grille combinée comporte
**12 559 colonnes de données**, dont quatre champs communs de provenance et de temps.
L'identifiant de ligne affiché par la grille constitue une colonne supplémentaire.

| Disposition réellement sélectionnée dans la GUI | Grilles | Lignes conservées |
| --- | ---: | ---: |
| Par fichier | 1 478 | 1 386 061 |
| Par famille | 56 | 1 386 061 |
| Combinée | 1 | 1 386 061 |

La disposition par famille regroupe les configurations et textes annexes derrière
« Supporting files ». Ses 40 schémas annexes ne sont pas imposés dans la navigation
principale. Les regroupements et recherches permettent toujours de les consulter.

Le nouvel import récupère **20 lignes SQLite et neuf événements Windows Timeline**
supplémentaires. Tous les nombres de lignes par lecteur sont conservés ou augmentés.
En particulier : EVTX **118 636**, MFT/USN **867 849**, SQLite **20 755** et
Windows Timeline **9**. Aucun lecteur ne termine avec le statut `error`.
Les 67 entrées `attention` restent visibles : un fichier vide ou seulement
partiellement interprété n'est pas présenté comme une lecture complète.

## Corrections et choix de conception

| Défaut ou difficulté | Correction et vérification |
| --- | --- |
| SQLite et Windows Timeline tentaient de créer leurs copies temporaires dans le pack d'outils non inscriptible | Répertoire temporaire propre à chaque exécution, dans le dossier de résultats ; import final sous UID 1000 et source montée en lecture seule. |
| Chemins SQLite contenant `%` ou `#`, et données validées seulement dans un WAL | URI correctement échappée ; copie privée DB/WAL lorsque le WAL contient des données, sans modifier la preuve. Régressions synthétiques sur le WAL ; les WAL de la collecte réelle sont vides. |
| `ntuser.dat.LOG1/LOG2` n'était pas associé à `NTUSER.DAT` sous Linux | Association des noms sans distinction de casse, après contrôle de signature. Les deux fichiers deviennent des compagnons de ruche. |
| Arbre encombré de schémas JSON et de noms internes | Noms des fichiers sources, familles cohérentes, annexes repliées par défaut, familles à un seul enfant aplaties ; recherche et développement manuel conservés. |
| Résumé d'import assimilant certains traitements sans analyse produite à une réussite | Comptage des sorties réellement produites ; distinction lecture, lecture partielle, échec et compagnons. |
| Lecteurs sans sortie conservés avec le statut « running » | Statut terminal `no_output`, et normalisation des anciens comptes rendus. Les 17 états concernés de cette collecte sont correctement présentés sans modifier les données analysées. |
| Plafonds fixes d'analyses et ancien budget de session trop étroit | Suppression des plafonds de nombre dans les sessions, imports, changements de vue et outils associés. Budget de métadonnées central de 64 Mio avec sauvegarde atomique ; régressions à 1 100 et 5 100 analyses. Ce budget est une protection de ressources, pas une promesse de ressources illimitées. |
| « Combinée » se divisait en 145 grilles sur cette collecte | Une table clairsemée conserve les positions et valeurs des colonnes d'origine. Les quatre champs communs sont physiques ; les autres utilisent une MAP typée. Les filtres, tris, groupes et expressions passent par les mêmes colonnes logiques du moteur. |
| Rendu de milliers de colonnes et confusion entre valeur absente et valeur non chargée | Fenêtre horizontale de colonnes, réponses projetées, espaces conservant la largeur de défilement ; chargement des détails complets à la sélection et avant copie. Gestionnaire de colonnes paginé, recherche et commande « Go to ». |
| Vue momentanément vide pendant un défilement continu ou après agrandissement | Redessin à chaque frame, observation des changements de largeur et temporisation séparée des requêtes de données. Deux régressions reproduites dans l'ancienne image, puis vérifiées dans la nouvelle. Les requêtes de filtre différées sont annulées lorsqu'Entrée lance déjà la recherche. |
| Détails d'un fichier très large en échec avec peu de mémoire | Lecture ponctuelle par lots de colonnes, sans augmenter le budget. Régression réelle à 3 000 colonnes et 64 Mio. |
| Export trop large pour une projection SQL ou pour une URL | Lecture clairsemée par petits lots ; omission des listes de colonnes inutiles et options JSON pour les listes longues. Export atomique et contrôle du contenu conservés. |
| Parcours de toutes les cellules vides de l'union | Recherche des champs renseignés directement dans les entrées de la MAP ; contrôle des espaces et tabulations. |
| Rapport susceptible d'associer les champs physiques de la MAP aux mauvaises étiquettes | Parcours explicite des champs logiques présents dans chaque enregistrement ; test des noms et valeurs dans le HTML produit. |
| Timeline combinée choisissant une colonne `Timestamp` sans rapport avec les autres fichiers | Horloge commune utilisée par défaut pour les analyses clairsemées, y compris quand les filtres de grille sont ignorés. Choix manuel toujours prioritaire. Même correction pour la date des résultats IOC. Régression avec une configuration contenant un faux `Timestamp`, puis contrôle graphique sur la collecte. |
| Annotations non reportées lors d'une reconstruction de grille | Références canoniques à l'analyse source, sa ligne et l'occurrence du champ ; transfert entre dispositions, conservation des notes sur les champs momentanément absents, propagation des suppressions. Tests sur les unions classiques et clairsemées, puis sur Security.evtx dans la GUI réelle. |
| Éditeur de note conservé après changement d'analyse | Fermeture des détails et invalidation de leur lecture en cours ; réinitialisation des panneaux dépendant des analyses après réorganisation. |

## Exactitude et intégrité

`final-combined-value-verification.json` enregistre la comparaison des nombres de
lignes des **1 478 analyses sources** avec l'union, puis de **2 984 enregistrements**
répartis dans ces analyses : **66 308 valeurs d'origine non NULL** comparées,
toutes identiques. Il s'agit d'un contrôle de l'assemblage par rapport aux analyses
sources, pas d'une validation indépendante de chaque interprétation des lecteurs.

La vérification indépendante des enveloppes actives des 177 EVTX retrouve
**118 636 événements**, sans taille de record invalide ni différence de CRC des
chunks examinés. Les différences initiales avec une lecture Dissect ont été
réconciliées avec les records actifs et les zones effacées/slack ; elles ne sont
pas présentées comme une perte d'événements du logiciel.

Les comparaisons indépendantes des exports tabulaires, des tables Firefox et de
16 enregistrements MFT nommés (noms, tailles et indicateurs de dossier) sont
conservées avec les résultats privés. Le
multiensemble des 1 247 empreintes d'entrées de lecteurs est identique entre les
deux derniers imports ; les comptages par lecteur ne diminuent pas.

L'archive originale reste en mode `0400`, montée `/evidence:ro`. Son SHA-256 est
inchangé après les opérations ; l'empreinte et le nom privé figurent uniquement
dans `final-source-integrity.json`. Les anciens dossiers de qualification générés
ont été retirés pour libérer de l'espace, après archivage de leurs métadonnées.
L'archive d'origine, le dossier final, les captures et les preuves de comparaison
sont conservés. Les autres instances de recette restent intactes.

## Résultats de tests vérifiables

| Rapport XML | Périmètre | Résultat |
| --- | --- | --- |
| `qualified-core-final.xml` | Moteur, lecteurs, sessions, annotations, portabilité et API Host | 1 342 réussis, 23 ignorés |
| `qualified-docker-final.xml` | Recette Chromium contre l’image Docker intermédiaire : grilles larges, dispositions, notes, cycle de vie et revue des commandes | 20 réussis |
| `viewport-docker-final.xml` | Dernière image : défilement continu, redimensionnement 1440p, notes, changement de disposition, cycle de vie et tris | 6 réussis |
| `combined-dates-final.xml` | Horloge commune, dates IOC, Timeline, rapports et API | 144 réussis |
| `final-empty-readers.xml` | États des lecteurs sans sortie, imports et routes HTTP | 120 réussis |
| `sparse-wide-export.xml` | Rapports, exports larges, colonnes vides et routes HTTP | 100 réussis |
| `layout-notes-final.xml` | Notes entre dispositions, union et dossier portable | 30 réussis |
| `wide-point.xml` | Moteur et détails larges avec budget contraint | 14 réussis |
| `registry-companions.xml` | Classification et protection des collectes | 19 réussis |

Ces exécutions se recoupent : leurs nombres ne doivent pas être additionnés.
Les premiers échecs reproduisant les défauts restent archivés, avec les relances
qui les résolvent. Les contrôles Ruff et de syntaxe JavaScript passent.

Les résultats des parcours métier complémentaires, leurs captures et reçus sont
consignés dans `workflows-final/results.json`. Les mesures de durée des changements
de disposition figurent dans `views-qualified/results.json`. Une reconstruction
complète de cette collecte prend plusieurs minutes ; le changement est effectué
dans l'interface courante, sans nouvel import des preuves, et n'est pas instantané.

La recette métier finale vérifie notamment :

- **27 événements 4625**, retrouvés dans les filtres de grille ; exports CSV et
  Excel de ces 27 lignes avec les **12 559 colonnes**, relus et contrôlés.
- **663 colonnes vides**, masquées puis restaurées ; parcours mesuré à environ
  cinq secondes sur cette collecte.
- Chasse IOC limitée aux 27 événements : **quatre correspondances attendues,
  quatre obtenues**, contrôle absent sans correspondance et dates sources présentes.
- Timeline : **1 386 061 enregistrements**, dont **139 138 datés** pour le champ de
  temps commun. Ce nombre correspond au contrôle ISO indépendant ; les autres
  lignes restent consultables avec l'option d'inclusion des non-datées. Le filtre
  de la grille ramène correctement la Timeline à **27 événements**.
- Rapport HTML d'un événement explicitement sélectionné : champs d'origine et
  EventId présents, représentation interne de la MAP absente.
- Après recréation du conteneur : **une grille, 1 386 061 lignes et 12 559
  colonnes**, annotation de ligne et annotation de cellule toujours attachées au
  même record d'origine de Security.evtx.
- Agrandissement réel de 1280 × 850 à **2560 × 1440**, sans zone de colonnes laissée
  vide dans la partie nouvellement visible.

Les captures définitives ont été reprises après stabilisation du rendu. Le fichier
`views-qualified/05-combinee-donnees-visibles.png` présente une sélection lisible de
colonnes et un filtre EVTX dans l'unique grille combinée ; les autres colonnes
restent disponibles. La disposition correspondante est fournie dans
`combined-investigation.layout.json`. Une capture intermédiaire prise pendant un
rafraîchissement ne sert pas de preuve finale.

## Reproduction et limites

Les régressions réutilisables sont dans `tests/core/test_collection_organization.py`,
`tests/core/test_collection.py`, `tests/core/test_engine.py`, `tests/test_reorganize.py`
et `tests/web/test_browser_wide_combined.py`. Les scripts de la recette privée et les
journaux d'import permettent de refaire les contrôles sur la collecte conservée.

Les captures proviennent du véritable Host conteneurisé à 1920 × 1080. Les captures
intermédiaires et les essais non concluants sont distingués des captures finales.
Les vérifications de cette passe complètent les deux recettes précédentes ; elles
ne constituent pas une preuve de toutes les combinaisons possibles de commandes,
ni une certification de chaque format forensique rencontré.

Les skills Cloud runtime/desktop accessibles ont servi à la prise en main de
l'environnement. Les quatre skills spécifiques cités dans la demande n'étaient
pas disponibles dans le catalogue ou les fichiers accessibles. La recette GUI a
donc utilisé Playwright avec le Chromium installé, directement contre Docker.
