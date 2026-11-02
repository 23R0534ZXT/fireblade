# Fireblade

[![Tests Windows et exécutable](https://github.com/23R0534ZXT/fireblade/actions/workflows/windows.yml/badge.svg?branch=main)](https://github.com/23R0534ZXT/fireblade/actions/workflows/windows.yml)

**Un outil forensic local pour Windows : parser une collecte, explorer ses résultats et examiner les alertes Hayabusa avec leur contexte EVTX.**

Choisissez un dossier d’artefacts, laissez les moteurs intégrés produire leurs résultats, puis travaillez dans Fireblade : recherche, filtres par colonne, conditions ET/OU/NON, tris, groupes, signets, notes et exports. Vous pouvez aussi ouvrir directement vos CSV, TSV, TXT délimités, XLS et XLSX.

Les données importées sont conservées dans des bases DuckDB `.timeline` sur disque. La grille affiche des pages ; filtres, comptages et exports portent sur le résultat complet. Le programme Windows est distribué dans **un seul `Fireblade.exe`**, avec ses moteurs et leurs dépendances. Les preuves et résultats restent des fichiers séparés.

## Télécharger et lancer

1. Ouvrez les [Releases](https://github.com/23R0534ZXT/fireblade/releases) et choisissez la préversion **Fireblade - prototype Windows** la plus récente. La Release du jeu de test contient des données, pas le programme.
2. Téléchargez `Fireblade.exe` et lancez-le sous Windows x64.
3. Ouvrez **Aide → Tutoriel complet — toutes les fonctionnalités**, ou **F1** pour le guide court.

Aucun Python, Excel ni runtime .NET séparé n’est nécessaire chez l’utilisateur pour les fonctions intégrées. Au démarrage, l’EXE extrait ses ressources dans un dossier temporaire Windows ; prévoyez l’espace disque correspondant. Le pack forensic rend le programme plus volumineux. Le fichier n’est pas signé avec un certificat de signature de code.

Une construction en cours sur `main` ne signifie pas que sa Release est prête : la publication attend les contrôles Windows. Les [artefacts Actions](https://github.com/23R0534ZXT/fireblade/actions/workflows/windows.yml) contiennent également un ZIP **Fireblade-exe**. Les archives GitHub « Source code » contiennent les sources à compiler.

## D’une collecte aux alertes et à leur contexte

1. Cliquez **Importer un dossier de collecte…**, puis choisissez le dossier contenant les artefacts. Les sous-dossiers sont parcourus ; les liens sont ignorés.
2. Choisissez **Un onglet par type d’artefact**, ou **Tout dans un seul onglet, regroupé par artefact**. Les résultats conservent leur provenance et les champs propres à chaque format.
3. Consultez le bilan dans **Collecte et détection**. Il distingue traitements terminés, avertissements, erreurs, fichiers non reconnus et sorties absentes. Les sorties originales des parseurs et leurs journaux sont conservés.
4. Cliquez **Analyser la collecte avec Hayabusa**. Les EVTX inventoriés sont vérifiés par SHA-256, copiés temporairement puis analysés ensemble avec les règles embarquées.
5. Dans **Alertes Hayabusa**, sélectionnez une détection, réglez la durée avant/après et cliquez **Voir le contexte de cette alerte**.
6. Le nouvel onglet **Contexte EVTX** affiche la chronologie des événements importés de la même machine, y compris dans d’autres journaux. **Ouvrir l’événement EVTX source** retrouve la ligne d’origine ; **Revenir aux alertes** conserve filtres et annotations.

Le contexte utilise **le fichier EVTX et EventRecordID**, avec contrôles de machine et d’EventID lorsqu’ils sont disponibles. Sa colonne épinglée distingue l’événement de l’alerte, les références candidates d’une agrégation et les voisins temporels. Un voisin n’est pas automatiquement suspect. La fenêtre vaut ±5 minutes par défaut, réglable de 1 minute à 24 heures, avec au maximum 1000 événements et signalement des limites.

Hayabusa analyse ici **les EVTX**. Les autres artefacts sont parsés et explorables ; les règles EVTX ne leur sont pas appliquées. Une détection reste une piste à examiner.

![Contexte d’une alerte Hayabusa : événement lié en gras, voisins temporels et accès à la source EVTX](docs/assets/fireblade-contexte-evtx.png)

Capture du parcours réel sur un EVTX public de démonstration, réalisée avec Qt hors écran sous Linux.

### Moteurs embarqués

| Moteur | Artefacts orientés par Fireblade |
|---|---|
| EvtxECmd | Journaux EVTX |
| AmcacheParser | Amcache / Inventory reconnus |
| AppCompatCacheParser | AppCompatCache dans une ruche SYSTEM |
| PECmd | Prefetch `.pf` |
| MFTECmd | `$MFT`, `$J`, `$Boot` et entrées reconnues |
| RECmd | Ruches de registre, batch Kroll et plugins RegistryPlugins |
| LECmd | Raccourcis LNK |
| JLECmd | Jump Lists automatiques et personnalisées |
| SrumECmd | `SRUDB.dat` |
| WxTCmd | `ActivitiesCache.db` |
| RBCmd | Métadonnées `$I` de la corbeille |
| RecentFileCacheParser | `RecentFileCache.bcf` |
| SQLECmd | Bases SQLite reconnues par ses maps |
| Hayabusa 4.3.1 | Détections et corrélations sur les EVTX inventoriés |

Les versions, sources et empreintes sont épinglées dans [la configuration des moteurs](config/forensic-toolchain.json). EvtxECmd et SQLECmd embarquent leurs maps ; RECmd embarque 70 plugins de registre. Un fichier SQLite n’est exploitable que si une map convient. Cette liste ne garantit pas toutes les variantes ni tous les formats acceptés en ligne de commande par chaque outil amont. Fireblade ne monte pas d’image disque.

## Explorer les résultats

| Besoin | Commande ou geste |
|---|---|
| Chercher dans une colonne | Champ **Contient…** sous son en-tête ; saisie différée ou Entrée |
| Trier rapidement | Flèches ▲ / ▼ à droite de l’en-tête ; menu pour le type Texte, Nombre ou Date ISO |
| Combiner des conditions | **Filtres → Éditeur ET / OU / NON** : blocs imbriqués, exclusions et aperçu du filtre |
| Regrouper | Glisser un en-tête dans la barre des groupes ; × retire un niveau |
| Lire une valeur complète | Panneau Détails ou **Afficher la cellule / JSON** |
| Garder une piste | Signet et note par ligne, ou annotations de la sélection |
| Chercher entre plusieurs analyses | **Filtres → Rechercher dans toutes les analyses** |
| Reprendre le travail | Vue nommée dans l’analyse et session `.fireblade-session` |
| Transmettre un résultat | Export CSV/XLSX filtré, annotations ou résumés |

La grille propose aussi tris multiples, résumés par groupe et pied global, dépliage paginé, colonnes épinglées à gauche/droite, hauteur de lignes, thèmes et règles de coloration locales/globales. Les conversions de dates créent des colonnes UTC distinctes ; les expressions permettent des colonnes calculées persistantes.

Les profils forensic organisent les colonnes sans constituer chacun un parseur brut. Fireblade importe certains layouts, préférences et sessions Timeline Explorer, ainsi que des lecteurs et fonctions DLL compatibles via ses helpers .NET. Cette compatibilité reste partielle : voir [les formats et limites](docs/development/COMPATIBILITE.md) et [les profils et plugins](docs/development/PLUGINS.md).

### Raccourcis principaux

| Action | Raccourci |
|---|---|
| Ouvrir des données / une analyse | Ctrl+O / Ctrl+Maj+O |
| Exporter les résultats | Ctrl+Maj+E |
| Effacer les filtres | Ctrl+E |
| Éditeur ET / OU / NON | Ctrl+Alt+F |
| Filtrer sur la cellule active | Ctrl+Maj+F |
| Recherche entre analyses | Ctrl+F |
| Enregistrer / charger une vue | Ctrl+S / Ctrl+L |
| Enregistrer la session | Ctrl+Maj+S |
| Marquer la sélection / retirer ses signets | Ctrl+Alt+B / Ctrl+Maj+M |
| Déplier / replier tous les groupes | Ctrl+M / Ctrl+K |
| Onglet suivant / précédent | Ctrl+Tab / Ctrl+Maj+Tab |
| Fermer / rouvrir un onglet | Ctrl+W / Ctrl+Maj+T |
| Guide utilisateur | F1 |

## Données et sauvegardes

Les sources sont lues sans réécriture et vérifiées par SHA-256. Les imports natifs préservent les valeurs texte, les zéros initiaux et les grands identifiants ; les cellules vides deviennent NULL. Pour Excel, la fidélité dépend aussi du type de cellule et du lecteur : les formules XLSX sont conservées comme texte, les formules XLS comme résultats mémorisés. Les macros ne sont pas exécutées.

| Élément | À conserver |
|---|---|
| `.timeline` | Données importées, provenance, annotations et vues |
| `.fireblade-session` | Références aux bases : conserver toutes les bases indiquées |
| Dossier de collecte Fireblade | `collection.json`, session, bases individuelles et organisées, CSV, contextes et journaux |
| Artefacts originaux | Nécessaires pour relancer Hayabusa ; les bases importées restent lisibles sans eux |
| Profil utilisateur | Préférences, règles globales, profils personnels et dispositions automatiques |

Les collectes sont créées dans `%LOCALAPPDATA%\Fireblade\Collectes`. **Reprendre une collecte…** demande son dossier de travail. Les fichiers `collection.json` et de session référencent des chemins : déplacer un dossier n’effectue pas une migration automatique de toutes les références.

Les réglages et analyses ordinaires se trouvent sous `%LOCALAPPDATA%\Fireblade`. Les sauvegardes de sessions ne contiennent pas les preuves. Les DLL tierces peuvent nécessiter leurs propres fichiers et dépendances, et s’exécutent avec les droits de l’utilisateur.

L’application traite les données localement. Les moteurs et règles du pack sont embarqués ; le parcours ordinaire n’a pas besoin de téléchargement. La construction, elle, récupère ses dépendances et les sources épinglées.

## Validation et limites connues

La validation vérifie les sources sur Windows avec Python 3.11, 3.12 et 3.13, puis le véritable EXE seul dans un dossier vide : ressources, moteurs, imports, affichage, sessions, annulations, annotations et exports. La publication dépend également des contrôles de stockage Windows, des lecteurs, des captures visuelles, du parcours avec 320 analyses et du jeu de 3 GiB.

Le contrôle forensic exige une sortie non vide de chacun des 13 parseurs, ouvre chaque résultat dans la grille et contrôle les valeurs affichées ; il vérifie aussi Hayabusa et son contexte. Les fixtures publiques sont épinglées et leur SHA-256 est vérifié. **Un test ajouté n’est pas une preuve qu’il est passé** : consultez le résultat du workflow du commit concerné.

Les résultats et limites sont détaillés dans [la validation forensic](docs/validation/COLLECTE-FORENSIC.md), [la validation Windows](docs/validation/WINDOWS.md) et [les rapports de qualification](docs/validation/QUALIFICATION.md). Les essais Linux et natifs Windows sont distingués. Des exemples représentatifs ne qualifient pas chaque version Windows, toutes les maps SQLite ou tous les fichiers corrompus.

La mémoire configurée est le buffer DuckDB, pas le plafond de RAM du programme ou des moteurs externes. Les groupes, caches, grands champs et plugins ajoutent leur coût. Prévoyez du disque pour les résultats, bases organisées et copies temporaires. La session est limitée à 1000 analyses. L’import n’est pas reprenable au milieu de l’écriture après une panne ; les traitements terminés d’une collecte restent conservés. Il n’y a pas d’export de rapport HTML/PDF.

### Jeu de test volumineux

[Télécharger le CSV de 3 GiB en ZIP](https://github.com/23R0534ZXT/fireblade/releases/download/test-data-3gib/Fireblade-test-3GiB.zip) · [Manifeste et empreinte](docs/validation/datasets/3gib.json) · [Exercice et résultats attendus](docs/guides/TESTER-3GIB.md)

Le jeu synthétique contient 2 441 216 enregistrements et 18 colonnes, pour 3 222 648 632 octets. Il sert aux contrôles de charge et ne remplace pas les fixtures des parseurs. Les mesures d’anciens commits ne qualifient pas automatiquement le binaire courant.

## Développement et construction

Depuis la racine du dépôt, sur Windows x64 avec Python 3.12 :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements/development.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m fireblade
.\.venv\Scripts\python.exe -m pytest -q
```

Pour reconstruire le fichier unique, installer aussi Git et le SDK .NET 10, puis lancer :

```powershell
py -3.12 -m scripts.windows.build
```

La construction prépare `.venv-build`, compile les moteurs et helpers, embarque le runtime .NET, les règles et maps, construit l’EXE et le contrôle après déplacement dans un dossier vide. Le livrable est `dist/Fireblade.exe` ; les rapports sont dans `artifacts/`. La compilation nécessite Internet. Elle n’est pas reproductible octet pour octet.

Le code est dans `src/fireblade`, les tests dans `tests`, les moteurs/fixtures épinglés dans `config`, les scripts de construction dans `scripts/windows`. Voir [Contribuer](docs/development/CONTRIBUER.md) et [Architecture](docs/development/ARCHITECTURE.md) pour les détails.

## Diagnostic et documentation

En cas de problème au démarrage : `%LOCALAPPDATA%\Fireblade\Journaux\demarrage.log`. Pour une collecte : bilan **Collecte et détection**, puis `parser.log` ou `hayabusa.log` dans son dossier de travail. Pour un problème reproductible, indiquez commit/version depuis **Aide → À propos**, Windows, étapes, résultat attendu et message exact.

Le contrôle intégré peut être lancé sur une nouvelle destination de rapport :

```powershell
.\Fireblade.exe --self-test-report "$env:TEMP\fireblade-controle.json"
```

Il utilise des données de qualification synthétiques et des artefacts publics embarqués ; il peut prendre du temps et de l’espace disque. Il n’analyse pas une collecte utilisateur.

- [Tutoriel complet](docs/guides/TUTORIEL-COMPLET.md) : collecte, détection, contexte, exploration, règles, sauvegardes et références.
- [Guide utilisateur](docs/guides/UTILISATION.md) : prise en main.
- [Index de la documentation](docs/README.md).
- [Compatibilité Timeline Explorer](docs/development/COMPATIBILITE.md).

## Licence

Le code Fireblade est sous [licence MIT](LICENSE). Les dépendances et moteurs gardent leurs licences respectives, dont l’AGPL pour Hayabusa. Les notices sont accessibles dans **Aide → Licences** et les sources Hayabusa embarquées sont exportables depuis **Collecte et détection**. Voir [les licences tierces](licenses/THIRD_PARTY.md).
