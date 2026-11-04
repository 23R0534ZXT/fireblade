# Audit complet de Fireblade 0.2.0 — 3 novembre 2026

> État historique avant correction. Les huit constats cumulés des deux passes ont ensuite été traités dans les sources ; voir les [correctifs et leur validation](20261104-v020-correctifs.md). L’EXE publié n’a pas été remplacé.

**La suite existante passe, mais les essais complémentaires révèlent trois problèmes prioritaires : arrêt du parcours NTFS, omission du journal SQLite WAL et lecture de fichiers locaux par une archive portable contenant une vue SQL.** Deux autres points concernent les résultats conservés après modification d’une source et une dépendance vulnérable.

Le code de l’application n’a pas été modifié. Cet audit ajoute un outil de reproduction et les preuves ci-dessous. Aucun correctif, déploiement, changement de release ou message GitHub n’a été effectué.

## Périmètre et provenance

- Sources examinées : `a968e21` ; version déclarée `0.2.0`.
- EXE publié : commit `43893ab8b5b7a6d501bc48dfa04591f694f5c5db`. Le code applicatif de `src/` est identique entre ce commit et les sources examinées ; les différences concernent la documentation et la publication.
- Exécutions nouvelles : Linux x86-64, Python 3.12.14, DuckDB 1.5.6, PySide6 6.12.0, Qt `offscreen`, quota de deux CPU et 8 Gio de RAM.
- Vérification des sources, tests du moteur, interface réelle Qt hors écran, fichiers malformés couverts par la suite, sauvegardes, disques, intégrité, exports, annulation, charge, dépendances, construction Python et documentation.
- Lecture manuelle ciblée des chemins d’import, requêtes, expressions, archives portables, sessions, cases, disques, sous-processus, lecteurs et rapports. Le scan statique couvre 33 194 lignes de code ; cela ne constitue pas une revue manuelle de chaque ligne.

[Synthèse JSON](20261103-v020-audit/summary.json) · [Essais indépendants](20261103-v020-audit/independent.json) · [Preuves d’interface](20261103-v020-audit/ui-probes.json).

## Résultats des vérifications

| Contrôle | Résultat observé |
|---|---|
| Suite complète | **1 177 réussis, 28 ignorés, zéro échec**, 276,47 s |
| Ruff, compilation Python, `pip check`, `git diff --check` | Réussis |
| CSV, comparaison indépendante | 40 scénarios × 37 lignes ; quatre séparateurs, cinq encodages, import direct et par petits lots ; cellules, export et réouverture identiques à `csv.reader` |
| Filtres | 250 arbres ET/OU/NON, sur 200 lignes, comparés à un évaluateur Python indépendant incluant la logique NULL |
| Dates | 300 horodatages, neuf décimales, décalages UTC, années 1601 à 2263 ; comparaison entière indépendante à la nanoseconde |
| Gros CSV | **3 275 068 297 octets, 8 380 000 lignes** ; intégrité, sept positions de pagination, groupes et export de 104 750 lignes vérifiés indépendamment |
| Annulation du gros CSV | Interruption réelle de DuckDB, rollback en 0,0753 s après demande, aucune table partielle, même base réutilisée pour un nouvel import |
| Journaux Linux | **4 Gio décodés et hachés**, 4 096 grandes lignes ; phase distincte de 200 000 lignes réellement importées, persistées et rouvertes |
| Chasse IOC | 50 000 IOC sur 100 000 lignes : 100 000 correspondances comptées, 1 000 détails conservés conformément à la limite demandée |
| Chronologie | 500 000 événements ; dernière page, entités, histogramme et chaque ligne d’export filtré vérifiés ; 4 951 correspondances attendues |
| Couverture | 120 000 lignes sur deux analyses ; comptes de dates, champs vides et filtres vérifiés ; export relu de 6 000 lignes, zéro erreur, sept avertissements attendus |
| Interface | La suite inclut 320 bases réelles, sessions, navigation, notes, thèmes, panneaux, rapports et traitements concurrents ; quatre captures supplémentaires de parcours ont été générées |
| Disques FAT / RAW | Tests existants réussis, dont FAT12 et disque MBR à deux partitions |
| ext4 public | Détection, parcours et lecture du contenu attendu réussis ; image inchangée. Zéro artefact sélectionné dans cette petite fixture |
| NTFS public | **Échec confirmé**, y compris par le parcours d’interface |
| E01 public | Décodage du conteneur de 4 Mio vérifié octet par octet selon le motif attendu ; cette fixture ne contient pas de système de fichiers |
| Wheel et sdist Python | Construction réussie ; ne qualifie pas une nouvelle construction de l’EXE Windows |
| Documentation du dépôt | 234 liens locaux contrôlés dans 47 Markdown, aucun fichier cible absent ; ancres et liens externes non exhaustivement contrôlés |

La suite Linux contient huit tests supplémentaires de publication par rapport aux 1 169 tests annoncés pour le commit Windows qualifié. Les résultats ne sont donc pas contradictoires.

Les 28 tests ignorés sont explicités dans [le journal complet](20261103-v020-audit/pytest.log) : hôtes et plugins .NET réels, Shellbags, sémantique Windows/SMB, encodeur GIF et fixture externe à l’emplacement prévu par un ancien test. Le CSV de charge créé pour cet audit est distinct de cette fixture externe.

## FB020-01 — P1 : une image NTFS arrête le parcours avant extraction

**Déclencheur :** analyser l’image NTFS publique de Dissect depuis « Analyser un disque », type image.

Dans `src/fireblade/core/disk.py:181`, le parcours appelle `child.is_junction()`. Sous Python 3.12, cette méthode existe sur le chemin virtuel. L’adaptateur Dissect appelle ensuite `NtfsFilesystemEntry.is_mount_point()`, mais cette méthode est absente de `dissect.target==3.25.1`.

Résultat : `AttributeError: 'NtfsFilesystemEntry' object has no attribute 'is_mount_point'`. La collecte passe à `error` et ne publie aucune analyse. L’interface reproduit l’échec et affiche le diagnostic dans son indicateur. L’image source reste inchangée.

L’inspection statique du véritable EXE publié confirme les trois éléments : Python 3.12, appel `is_junction` dans Fireblade, et méthode `is_mount_point` appelée mais absente dans la classe embarquée. Cela établit la présence du code défectueux dans le binaire ; l’EXE n’a pas été exécuté sous Windows pendant cet audit.

**Correction recommandée :** séparer le contrôle des jonctions des chemins natifs et celui des chemins virtuels Dissect. Le `is_symlink()` NTFS de cette version reconnaît déjà les points de montage. Ajouter un test sur une vraie petite image NTFS et conserver le refus de suivre les liens ; ne pas simplement ignorer toute exception.

Preuves : `disk_matrix` dans [independent.json](20261103-v020-audit/independent.json), [capture de l’échec](20261103-v020-audit/ntfs-failure.png), [inspection de l’EXE](20261103-v020-audit/exe-static.json).

## FB020-02 — P1 : les transactions SQLite présentes dans le WAL sont omises

**Déclencheur :** analyser un disque ou dossier contenant une base telle que `History` et son journal `History-wal`, avec une transaction validée encore présente dans le WAL.

Le sélecteur de `src/fireblade/core/disk.py:20` reconnaît plusieurs bases SQLite, mais pas leurs compagnons `-wal`. Le parcours ne copie explicitement que les compagnons des ruches de registre (`disk.py:203`).

Reproduction avec une vraie base SQLite en mode WAL : création de la table, checkpoint, insertion validée d’une visite puis conservation de la connexion ouverte. La source contient **une visite**, sa copie Fireblade contient **zéro visite**. Avant toute ouverture de la copie par SQLite, seul `History` est présent dans le dossier extrait. Le SHA-256 du fichier principal est correct et le bilan d’extraction ne comporte aucune erreur.

Ce résultat démontre une omission à la couche d’extraction, avant le parseur natif. Il ne prétend pas avoir exécuté SQLECmd sous Linux. Une copie exacte du fichier principal ne suffit pas à prouver que l’état logique de la base a été conservé.

**Correction recommandée :** inventorier et copier les compagnons utiles des bases SQLite, notamment le WAL et les journaux de rollback, en conservant leur provenance. Contrôler leur cohérence comme un ensemble et signaler explicitement une copie incomplète ou changeante. Préserver la lecture seule des originaux.

Preuve : `sqlite_wal` dans [independent.json](20261103-v020-audit/independent.json), source `1`, copie `0`, liste des fichiers relevée avant lecture.

## FB020-03 — P1 : une archive portable peut lire un fichier du poste qui l’ouvre

**Déclencheur :** importer puis ouvrir une archive `.fireblade-case` spécialement construite, dont le fichier `.timeline` déclare `events` comme vue SQL utilisant `read_text()`.

`src/fireblade/core/case_package.py:289` ouvre les bases fournies et contrôle certaines métadonnées, sans imposer que les objets attendus soient des tables physiques. `src/fireblade/core/engine.py:57` laisse les accès externes DuckDB autorisés. La requête d’affichage exécute donc la vue stockée dans la base.

La reproduction utilise uniquement un fichier témoin synthétique **hors de l’archive**, contenant `SYNTHETIC-LOCAL-MARKER-ONLY`. Le ZIP ne déclare qu’une base et un manifeste, avec taille et SHA-256 corrects. L’import réussit. L’ouverture réelle du case dans l’interface affiche ensuite le contenu du témoin dans la grille, sans erreur d’ouverture. Aucune DLL ni aucun plugin n’est nécessaire.

**Impact :** une enquête reçue d’un tiers peut faire apparaître comme des données d’analyse un contenu local accessible à l’utilisateur. Une consultation ou un export ultérieur peut divulguer ce contenu. Les sommes de contrôle vérifient les octets fournis par l’auteur ; elles ne rendent pas les objets SQL inertes. Aucun secret réel, aucune exécution de commande et aucune exfiltration réseau n’ont été utilisés ou démontrés.

**Correction recommandée :** ouvrir les bases reçues avec des restrictions d’accès externe avant toute lecture de leurs objets ; valider strictement le schéma attendu, y compris le type des objets, et rejeter les vues/macros inattendues. Vérifier aussi les chemins d’ouverture directe `.timeline` et les sessions. Tester la même archive hostile contre l’EXE corrigé.

Preuves : `hostile_package` dans [independent.json](20261103-v020-audit/independent.json), [résultat UI](20261103-v020-audit/ui-probes.json), [capture de la grille](20261103-v020-audit/hostile-package-grid.png).

## FB020-04 — P2 : une source modifiée reste dans la session de collecte classique

**Déclencheur :** modification d’un CSV entre la fin de son import et le dernier contrôle SHA-256 de la collecte classique.

La reproduction injecte cette modification de manière déterministe après l’import réel. `src/fireblade/core/collection.py:373` détecte correctement le changement et marque le fichier `error`, avec « Source modifiée pendant le traitement ; résultats à vérifier ». Cependant, le hook de publication de la classe de base (`collection.py:270`) ne retire pas ses documents : la session sauvegardée conserve l’analyse et le statut global devient `complete`.

Il existe bien un avertissement ; ce n’est donc pas un défaut silencieux. L’incohérence concerne la publication et la réouverture de résultats associés à un contrôle d’intégrité échoué. Le parcours disque retire déjà ces documents, contrairement au parcours classique.

**Correction recommandée :** appliquer une politique commune de publication des résultats vérifiés. Si des résultats à vérifier sont conservés pour l’analyste, les isoler et conserver leur état d’intégrité à la réouverture. Ajouter une régression sur la session produite, pas uniquement sur le message d’erreur.

Preuve : `changed_source` dans [independent.json](20261103-v020-audit/independent.json), un document sauvegardé malgré `file_status=error`.

## FB020-05 — P2 : `idna==3.11` possède une vulnérabilité connue

L’audit des versions de `requirements/runtime.txt` signale **CVE-2026-45409 / GHSA-65pc-fj4g-8rjx**, déni de service par traitement coûteux de certaines entrées Unicode. La version corrigée indiquée est **3.15**. La dépendance est épinglée dans `requirements/runtime.txt:10` et `pyproject.toml`.

`normalize_domain()` dans `src/fireblade/core/ioc_hunt.py:58` appelle `idna.encode()` après une limite de 1 024 caractères sur l’hôte. Cette limite réduit l’exposition par rapport aux entrées arbitrairement longues décrites par l’avis. **Un déni de service exploitable dans Fireblade n’a pas été démontré.** Il reste recommandé de mettre à jour la dépendance et de rejouer les essais IDNA/IOC.

Le scanner affiche deux entrées pour ce paquet, mais elles portent le même identifiant et les mêmes alias : il s’agit d’**un avis unique**, pas de deux vulnérabilités distinctes.

Preuve : [runtime-dependencies.json](20261103-v020-audit/runtime-dependencies.json), [avis de sécurité](https://github.com/advisories/GHSA-65pc-fj4g-8rjx).

Le scan de l’environnement de développement relève aussi six avis uniques sur `pip==25.0.1`. C’est un sujet de maintenance du venv local ; `pip` n’est pas présent dans l’archive Python de l’EXE inspecté. Il n’est pas compté comme défaut du runtime publié. [Scan de l’environnement](20261103-v020-audit/installed-dependencies.json).

## Charge, mémoire et intégrité

| Mesure | Valeur |
|---|---:|
| Import CSV de 3,05 Gio, avec deux passes SHA-256 | 125,239 s |
| Première page | 0,007 s |
| Groupement sur deux colonnes | 0,020 s |
| Première page triée numériquement | 1,036 s |
| Compte filtré | 0,011 s |
| Pic RSS échantillonné du benchmark CSV | 324,1 Mio |
| Base produite | 100 151 296 octets |
| Indexation de la chronologie de 500 000 lignes | 14,814 s |
| Pic RSS du benchmark chronologie, budget DuckDB 64 Mo par base | 204,6 Mio |
| Décodage/hachage des 4 Gio de journaux | 20,929 s |
| Import persistant des 200 000 lignes Linux | 21,787 s |
| Scan de 50 000 IOC sur 100 000 lignes | 5,85 s |

Plusieurs charges ont été lancées simultanément. Les données sont synthétiques, répétitives et compressibles ; ces mesures ne prédisent pas une collecte réelle et ne comparent pas Fireblade à un autre produit. Le budget DuckDB ne limite pas toute la mémoire du processus.

Le contrôle indépendant du gros CSV vérifie les valeurs et l’ordre, et pas seulement le compte produit par Fireblade. Son export compare chaque ligne à la structure connue du jeu. Les SHA-256 des sources sont contrôlés après les opérations. Le test Linux de 4 Gio contourne volontairement l’écriture CSV pour mesurer le décodage avec un coût disque borné ; les 200 000 lignes persistées constituent une phase distincte.

Preuves : [CSV](20261103-v020-audit/benchmark-3gib.json), [annulation](20261103-v020-audit/cancellation-3gib.json), [chronologie](20261103-v020-audit/timeline-500k.json), [Linux](20261103-v020-audit/linux-logs.json), [IOC](20261103-v020-audit/ioc-50k.json), [couverture](20261103-v020-audit/coverage-120k.json).

## Binaire publié et contrôles Windows

Le fichier téléchargé depuis [la release v0.2.0](https://github.com/23R0534ZXT/fireblade/releases/tag/v0.2.0) mesure **268 755 668 octets**. Son SHA-256 calculé est :

```text
cd0bc25997ad63c6b5cfea47c0e27f10f4e92cffe79c46575293680333df3502
```

Il correspond au digest GitHub et aux notes de publication. Les ressources PE indiquent `FileVersion=0.2.0`, `ProductVersion=0.2.0`, architecture x64 et sous-système graphique. L’archive contient 8 449 entrées et embarque Python 3.12. Le binaire n’a pas de signature Authenticode, conformément au statut de prototype annoncé.

La [qualification Windows 41673982489](https://github.com/23R0534ZXT/fireblade/actions/runs/41673982489) a été consultée via le connecteur GitHub. Les neuf contrôles requis sont `success` : syntaxe, trois versions Python, EXE autonome, UNC/chemins longs, lecteurs natifs, apparences/3 Gio et 320 analyses. Il s’agit de résultats Windows antérieurs à cet audit, pas d’une nouvelle exécution Windows.

Les nouveaux essais expliquent pourquoi cette CI verte ne suffit pas à qualifier tous les parcours disque : les tests disque existants utilisent surtout FAT et des sources montées, et ne détectent pas le chemin NTFS fautif.

Preuves : [release](20261103-v020-audit/release.json), [empreinte calculée](20261103-v020-audit/exe-hash.json), [inspection statique](20261103-v020-audit/exe-static.json).

## Analyse statique et limites

Bandit remonte 309 alertes heuristiques : 224 basses, 85 moyennes, aucune haute selon sa propre classification. Ce total **n’est pas un nombre de failles**. Une part importante concerne les assemblages SQL paramétrés, les appels de sous-processus avec listes d’arguments et le parsing XML avec refus explicite des DTD. Les trois constats prioritaires ci-dessus viennent des reproductions ciblées ; l’absence d’alerte haute du scanner ne les invalide pas. [Comptages statiques](20261103-v020-audit/static-analysis.json).

Cet audit ne fournit pas une couverture de lignes mesurée ni une garantie d’absence d’autres défauts. Il ne comprend pas de nouvelle exécution native Windows, de disque physique réel, de panne électrique, de corruption à tous les points d’écriture, ni de test humain prolongé. Les moteurs Windows/.NET ont été vérifiés par leurs résultats CI existants, pas réexécutés dans cet environnement Linux. Le cas WAL est un contrôle d’extraction ; le cas E01 est un contrôle de conteneur, pas une qualification de toutes les images E01. ext4 n’est couvert que par une petite fixture et sa lecture attendue.

## Reproduire

Depuis la racine du dépôt, avec les dépendances de développement installées et des répertoires neufs :

```bash
.venv/bin/python -m pytest -q --durations=25 -ra
.venv/bin/python -m ruff check src scripts tests
.venv/bin/python -m pip check

PYTHONPATH=src .venv/bin/python -m scripts.benchmarks.benchmark \
  --directory /tmp/fireblade-v020-large --gib 3.05

PYTHONPATH=src .venv/bin/python -m scripts.benchmarks.audit_v020 \
  --directory /tmp/fireblade-v020-independent \
  --large-directory /tmp/fireblade-v020-large \
  --fetch-fixtures /tmp/fireblade-v020-public-images

PYTHONPATH=src .venv/bin/python -m scripts.benchmarks.verify_import_cancel \
  --source /tmp/fireblade-v020-large/benchmark.csv \
  --directory /tmp/fireblade-v020-cancel

PYTHONPATH=src .venv/bin/python -m scripts.benchmarks.benchmark_timeline \
  --directory /tmp/fireblade-v020-timeline --rows 500000

PYTHONPATH=src .venv/bin/python -m scripts.benchmarks.linux_logs \
  --directory /tmp/fireblade-v020-linux --gib 4 --import-rows 200000 \
  --report /tmp/fireblade-v020-linux.json

PYTHONPATH=src .venv/bin/python -m scripts.benchmarks.ioc_hunt
PYTHONPATH=src .venv/bin/python -m scripts.benchmarks.coverage
```

L’outil `audit_v020` retourne **1 lorsque les constats sont reproduits**, **2 pour une erreur imprévue du banc d’essai**, et 0 si aucun constat n’est déclenché. Les quatre groupes de constats reproduits sont séparés des quatre groupes de contrôles réussis dans son JSON. Sans les options de charge et d’images, il fonctionne avec des données synthétiques locales et ne télécharge rien.

Les téléchargements publics sont optionnels, épinglés par commit et vérifiés par SHA-256 Git LFS. Leur provenance exacte figure dans [public-fixtures.json](20261103-v020-audit/public-fixtures.json). `--disk-fixtures` réutilise un dossier déjà préparé. L’oracle de charge attend précisément le jeu généré avec `--gib 3.05` par le benchmark de cette version.

Priorité de correction proposée : **FB020-03, FB020-01 et FB020-02**, puis FB020-04 et la mise à jour IDNA. Rejouer les reproductions avant une nouvelle qualification Windows et toute publication corrigée.

## Complément du 4 novembre 2026

La [seconde passe fonctionnelle](20261104-v020-functional-audit.md) atteint 1 200 tests distincts réussis, exerce les hôtes .NET réels, les parseurs compatibles Linux et de nouveaux parcours d’interface. Sa [matrice de 59 familles](20261104-v020-functional-matrix.md) précise les succès et les limites. Trois défauts supplémentaires de protection des destinations y sont documentés (FB020-06 à FB020-08). Les chiffres du présent rapport restent ceux de la première passe.
