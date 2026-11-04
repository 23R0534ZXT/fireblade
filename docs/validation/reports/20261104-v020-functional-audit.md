# Fireblade 0.2.0 — seconde passe fonctionnelle, 4 novembre 2026

> État historique avant correction. Les huit constats cumulés ont ensuite été traités dans les sources ; voir les [correctifs et leur validation](20261104-v020-correctifs.md). L’EXE publié n’a pas été remplacé.

**1 200 tests distincts réussissent désormais, cinq restent ignorés. Trois nouveaux défauts de protection des destinations sont confirmés.** Le code applicatif reste inchangé ; les outils d’audit et les preuves sont ajoutés au dépôt.

La [matrice détaillée](20261104-v020-functional-matrix.md) relie **59 familles de fonctionnalités** aux scénarios, résultats et tests. Elle complète le [premier audit](20261103-v020-audit-complet.md), dont les cinq constats restent ouverts. Une famille « exercée » signifie que les scénarios décrits ont été exécutés ; cela ne couvre pas toutes les combinaisons ni toutes les plateformes.

## Ce qui a été ajouté à la première passe

| Vérification nouvelle | Résultat |
|---|---|
| Suite entière instrumentée | 1 177 réussis, 28 ignorés, zéro échec en 306,62 s |
| Hôte réel .NET et lecteurs/fonctions personnalisés | 43 tests réussis, un ignoré ensuite exécuté séparément |
| Shellbags/WebCache et changements répétés de case | Cinq tests réussis, dont trois auparavant ignorés |
| Lecture bornée d’en-tête du CSV de plus de 3 Gio | Test auparavant ignoré, désormais réussi en réutilisant le CSV de la première passe |
| Cumul après dédoublonnage des identifiants pytest | **1 200 réussis, cinq ignorés, zéro échec** ; ce n’est pas une seule invocation pytest |
| Menus principaux | 101 entrées inventoriées : 95 déclenchées, trois commandes de cycle de vie vérifiées séparément, deux désactivées selon le contexte, un diagnostic attendu dans le checkout source |
| Menus contextuels | 85 déclenchements sur cellule, en-tête simple, groupé ou épinglé ; trois diagnostics attendus pour des valeurs qui ne sont pas des chemins |
| Dialogues acceptés | Recherche interanalyses, choix des dates de chronologie, récupération, modification/archivage/réactivation de case |
| JSON/XML | Formatage valide et refus explicite du JSON malformé et des DTD XML |
| Démarrage réel | Bootstrap, animation activée/désactivée, case obligatoire et import différé du fichier fourni en argument |
| Transport entre fonctionnalités | Colonne calculée, filtres, épinglage des deux côtés, hauteurs auto, note, IOC CSV/XLSX, couverture, HTML/PDF, archive portable, réouverture et chronologie reconstruite |
| Rendu supplémentaire | 24 thèmes et deux modes standard, aux facteurs 1,25 et 2 ; contraste vérifié, soit 52 captures de modes/thèmes plus deux dialogues de préférences |
| GIF sans encodeur Qt | GIF89a connu décodé et enveloppe canonisée en PNG, sans dépendre de l’encodeur absent |
| Parseurs réels | Quinze commandes d’aide réussies ; dix des treize EZ Tools produisent des résultats non vides sous Linux, plus Shellbags et WebCache |
| Détection et contexte réels | Hayabusa Linux 4.3.1 avec les règles embarquées : deux alertes, contexte de treize événements ; aperçu Qt et conservation explicite vérifiés |

Les tests .NET et navigateur comprennent des contrôles déjà réussis auparavant. Leur contribution au cumul est calculée par identifiant, sans les compter deux fois. **23 des 28 tests initialement ignorés ont pu être exercés.**

Preuves : [synthèse](20261104-v020-functional/summary.json), [suite complète](20261104-v020-functional/full-suite.log), [plugins .NET](20261104-v020-functional/dotnet-tests.log), [navigateurs](20261104-v020-functional/browser-tests.log), [menus/dialogues](20261104-v020-functional/menus-and-dialogs.json), [menus contextuels](20261104-v020-functional/context-menus.json), [démarrage](20261104-v020-functional/startup-animation.json), [transport et protections](20261104-v020-functional/cross-feature-and-protection.json).

Les commandes de menus ouvrant un sélecteur de fichier ont été annulées dans le test de déclenchement ; les éditeurs modaux ont été ouverts puis annulés. Ces contrôles repèrent les erreurs de branchement et de cycle de vie. La matrice les complète par les tests qui importent réellement les données, acceptent les dialogues ou contrôlent les résultats. Les lancements d’outils externes ont été interceptés pour ne pas exécuter un fichier de preuve ni ouvrir un navigateur pendant l’audit.

## FB020-06 — P1 : un export peut remplacer une source brute de collecte inventoriée

**Reproduction :** créer un vrai ZIP `var-log.zip` contenant `var/log/auth.log`, l’importer comme collecte, ouvrir son analyse puis sélectionner le ZIP original comme destination d’export CSV.

La garde `src/fireblade/ui/export_commands.py:46` protège les sources déclarées par les analyses ouvertes. Après passage par un parseur, cette source est le CSV généré ; l’archive originale reste référencée dans l’inventaire de collecte. Elle n’est pas ajoutée aux destinations protégées.

Résultat : la garde retourne `True`, alors que le fichier figure dans `collection.report['files']`. L’export remplace le ZIP brut par un CSV et annonce **« Export vérifié : 1 lignes »**. Les empreintes avant/après sont différentes. La vérification du contenu exporté ne protège donc pas l’intégrité de la source remplacée.

**Correction recommandée :** protéger aussi les sources brutes des collectes connues du case, y compris archives et compagnons, et leurs alias par identité de fichier. Effectuer le refus avant toute écriture. Tester au minimum un artefact natif et une archive Linux, avec chemins directs et liens physiques.

Preuve : `raw_collection_export` dans [source-protection.json](20261104-v020-functional/source-protection.json).

## FB020-07 — P1 : l’export des sources Hayabusa contourne les gardes sur les preuves

**Reproduction :** depuis une analyse valide, choisir son CSV source comme destination de **Aide → Exporter les sources Hayabusa…**.

`src/fireblade/ui/collection.py:274` utilise directement `shutil.copyfile(source, target)`, sans appeler la protection commune des destinations. Le contrôle a utilisé la véritable archive de sources Hayabusa extraite de l’EXE dont l’empreinte avait été vérifiée.

Résultat : le CSV source devient un ZIP. Aucune erreur n’est émise ; le message annonce **« Sources Hayabusa exportées »**. Le SHA-256 change de `e0f2755f…` à `12d9d21d…` dans cette reproduction. Le chemin choisi est précisément celui que l’export CSV normal refuserait.

**Correction recommandée :** passer par la même garde de destinations que les autres exports, élargie aux sources brutes et aux fichiers internes. Écrire dans un temporaire puis publier atomiquement, en conservant la destination précédente en cas d’échec.

Preuve : `hayabusa_source_export` dans [source-protection.json](20261104-v020-functional/source-protection.json), avec empreintes complètes et message de réussite.

Ces deux défauts nécessitent de choisir un fichier source existant comme destination et, selon le sélecteur système, de confirmer son remplacement. Ils ne provoquent pas une modification spontanée pendant l’analyse. Les sélecteurs ont été pilotés pour retourner ces destinations ; les gardes applicatives et les écrivains réels ont ensuite été exécutés. Tous les originaux de ces reproductions étaient jetables et leurs octets ont été restaurés avant fermeture de l’application.

## FB020-08 — P2 : trois écrivains peuvent remplacer des fichiers internes du case

Une matrice de seize essais compare quatre écrivains et quatre destinations connues : `case.json`, `coverage-state.json`, `timeline-state.json` et le fichier des règles globales.

| Écrivain | case.json | Couverture | Chronologie | Règles globales |
|---|---|---|---|---|
| Export CSV via l’interface | Refus, conservé | Refus, conservé | Refus, conservé | Refus, conservé |
| Sauvegarde de session Fireblade avec destination explicite | **Remplacé** | **Remplacé** | **Remplacé** | **Remplacé** |
| Export de session TLE | **Remplacé** | **Remplacé** | **Remplacé** | **Remplacé** |
| Export de règles globales | **Remplacé** | **Remplacé** | **Remplacé** | Refus, conservé |

Les chemins concernés sont `src/fireblade/ui/workspace.py:159`, `src/fireblade/ui/exploration.py:512`, `src/fireblade/core/tle_session_export.py` et `src/fireblade/ui/shared_rules.py:100`. Ces écrivains ont leurs propres listes de protection, plus étroites que `export_destination_is_safe()`.

Lors du remplacement de `case.json` par une session Fireblade, la sauvegarde suivante signale **« Fiche de case invalide »**, après écrasement. Les autres destinations testées peuvent être remplacées sans erreur immédiate. L’historique peut permettre une récupération du case, mais ne rend pas cette opération sûre et ne reconstitue pas nécessairement les fichiers de configuration annexes.

**Correction recommandée :** centraliser la protection de toutes les écritures choisies par l’utilisateur : sources, analyses, règles, manifeste, états, sessions internes et historique. Un refus doit précéder le remplacement. Ajouter les seize combinaisons comme régressions ciblées, en conservant les succès légitimes vers un nouveau fichier externe.

Preuve : groupe `protection` dans [cross-feature-and-protection.json](20261104-v020-functional/cross-feature-and-protection.json). Les métadonnées synthétiques ont été restaurées entre les essais pour éviter de contaminer les résultats suivants.

## Parseurs effectivement exécutés

Les assemblies proviennent de l’EXE 0.2.0 publié, SHA-256 `cd0bc25997ad63c6b5cfea47c0e27f10f4e92cffe79c46575293680333df3502`. Ils ont été exécutés avec .NET Linux **10.0.14**, installé par le SDK **10.0.403**. Les moteurs n’ont pas été simulés.

| Lecteur | Lignes importées | Observation |
|---|---:|---|
| EvtxECmd | 13 | Lecture EVTX réussie |
| AmcacheParser | 2 | Fixture embarquée |
| AppCompatCacheParser | 718 | Deux fichiers SYSTEM soumis |
| PECmd | 2 | Fixture Prefetch décompressée |
| MFTECmd | 117 | MFT publique du pack |
| RECmd | 14 510 | Deux SYSTEM réussis ; un UsrClass sale sans LOG refusé, comme attendu |
| LECmd | 1 | LNK |
| JLECmd | 1 | Jump List |
| RBCmd | 1 | Métadonnée de corbeille |
| RecentFileCacheParser | 6 | Fichier BCF |
| Shellbags | 523 | Lecture avec avertissement de ruche sale attendu |
| WebCache | 1 612 | Lecteur ESE Python |
| SQLECmd | Non qualifié ici | `SQLite.Interop.dll` Windows n’est pas un binaire ELF |
| WxTCmd | Non qualifié ici | Bibliothèque native Linux `e_sqlite3` absente du pack Windows |
| SrumECmd | Non qualifié ici | Le moteur indique explicitement nécessiter les bibliothèques ESE Windows |

Le script conserve ces refus comme tels : il ne les transforme pas en réussites. Le refus RECmd du UsrClass sale est distinct des trois limites de plateforme. Toutes les empreintes des sources de cette collecte restent inchangées après les parseurs, Hayabusa et le contexte.

Le binaire Linux Hayabusa **4.3.1** provient de sa release officielle ; son ZIP a été vérifié avec le digest publié `a4fbdae9b13a5fe0f3b3d98981dd18775f50e5402cf3dee3ba85d4ecd252370e`. Les règles proviennent du pack Fireblade. Il a produit deux alertes, dont « Important Log File Cleared », associée à un événement de référence et treize événements de contexte. L’interface a affiché l’aperçu sans ajouter prématurément de document, puis a conservé le contexte à la demande.

Preuves : [résultats complets](20261104-v020-functional/native-readers.json), [provenance des assemblies](20261104-v020-functional/native-provenance.json), [Hayabusa Linux](20261104-v020-functional/hayabusa-linux.json), [contexte dans Qt](20261104-v020-functional/native-context-ui.json). Les quatre journaux de refus sont conservés dans le même dossier.

## Mesure de couverture

| Couche Python | Instructions exécutées | Couverture des instructions | Branches exécutées | Couverture des branches |
|---|---:|---:|---:|---:|
| Moteur `core/` | 8 097 / 8 909 | **90,89 %** | 3 257 / 4 110 | 79,25 % |
| Interface `ui/` | 6 743 / 7 694 | **87,64 %** | 1 619 / 2 218 | 72,99 % |
| Runtime | 63 / 115 | 54,78 % | 18 / 42 | 42,86 % |
| Outils de qualification embarqués | 1 397 / 2 609 | 53,55 % | 142 / 360 | 39,44 % |
| Ensemble instrumenté | 16 301 / 19 330 | **84,33 %** | 5 036 / 6 730 | **74,83 %** |

Ces métriques proviennent de Coverage.py avec les branches activées, après fusion des exécutions. Le détail par fichier, instructions manquantes et branches est dans [coverage.json](20261104-v020-functional/coverage.json). Les outils de qualification Windows restés inactifs sont inclus dans le total, ce qui explique une partie de sa différence avec le moteur.

La mesure ne couvre pas le code C#, les binaires natifs, ni toutes les fonctions Python exécutées dans les threads créés par Qt : notamment `QRunnable.run` échappe à l’instrumentation automatique normale. Les tests en vérifient néanmoins les résultats. Ce sont des chiffres d’instrumentation, pas un pourcentage de fonctionnalités garanties ni une preuve d’exhaustivité.

## Limites restantes, identifiées précisément

Quatre tests pytest nécessitent Windows : chemins longs, UNC/SMB, emplacement LocalAppData natif et verrouillage d’un fichier à l’export. Le cinquième test ignoré dépend de l’encodeur GIF Qt absent ; [un essai séparé du décodeur GIF](20261104-v020-functional/gif-decoder.json) a réussi avec des octets connus, sans prétendre avoir exécuté ce test paramétré.

Il n’y a toujours pas de nouvelle exécution du véritable EXE Windows dans cet environnement, ni de qualification de périphérique physique réel, de CLR4, de tous les systèmes de fichiers/images E01, des gestes humains de l’Explorateur ou de sessions de plusieurs jours. Les résultats Windows antérieurs restent ceux cités dans le premier audit. SQLECmd, WxTCmd et SrumECmd demandent encore une exécution native adaptée pour cette seconde passe.

Les fonctionnalités couvertes par les données de la première passe ne sont pas artificiellement recomptées comme nouvelles charges : les 3,05 Gio de CSV, 4 Gio décodés, 50 000 IOC et 500 000 événements de chronologie restent documentés dans ce rapport antérieur.

## Reproduire les nouveaux parcours

Choisir des répertoires neufs et travailler depuis la racine du dépôt :

```bash
PYTHONPATH=src .venv/bin/python -m scripts.benchmarks.audit_functional \
  --directory /tmp/fireblade-functional \
  --hayabusa-source /chemin/pack-verifie/Hayabusa-source.zip

PYTHONPATH=src .venv/bin/python -m scripts.benchmarks.audit_entrypoint \
  --directory /tmp/fireblade-startup-animation

PYTHONPATH=src .venv/bin/python -m scripts.benchmarks.audit_entrypoint \
  --directory /tmp/fireblade-startup-no-animation --no-animation

QT_SCALE_FACTOR=1.25 PYTHONPATH=src .venv/bin/python -m scripts.benchmarks.preview_themes \
  --output /tmp/fireblade-themes-125

QT_SCALE_FACTOR=2 PYTHONPATH=src .venv/bin/python -m scripts.benchmarks.preview_themes \
  --output /tmp/fireblade-themes-200

PYTHONPATH=src .venv/bin/python -m scripts.benchmarks.audit_native_readers \
  --toolpack /chemin/pack-extrait-verifie \
  --dotnet /chemin/dotnet-linux \
  --hayabusa /chemin/hayabusa-4.3.1-linux \
  --directory /tmp/fireblade-native-readers
```

`audit_functional` retourne 1 pour un constat attendu, 2 pour une erreur imprévue, et 0 si aucun constat ne se déclenche. `--only menus dialogs context` permet de rejouer uniquement les parcours réussis. Sans `--hayabusa-source`, le cas d’export de cette archive n’est pas exercé ; le contrôle des sources brutes de collecte l’est toujours.

`audit_native_readers` utilise les fixtures et configurations du pack vérifié ; les bibliothèques natives de Windows ne deviennent pas compatibles Linux par extraction. Son code de sortie 1 et ses refus détaillés doivent être conservés dans le bilan.

Les tests .NET supplémentaires utilisent les variables documentées par le dépôt : `FIREBLADE_DOTNET`, `FIREBLADE_PLUGIN_HOST`, `FIREBLADE_PLUGIN_FIXTURE` et `FIREBLADE_SHELLBAGS_HOST`. Les builds, SDK, ressources extraites et grandes données de cet audit restent dans `/workspace/scratch` ; seuls les scripts et rapports ont été ajoutés au dépôt.

Les huit constats cumulés restent à corriger avant une nouvelle qualification de publication. Pour les nouveaux défauts, la priorité est de rendre commune et complète la protection des destinations, puis de rejouer les preuves de préservation des sources et du case.
