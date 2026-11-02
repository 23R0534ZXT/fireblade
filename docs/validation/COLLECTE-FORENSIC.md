# Validation du parcours collecte forensic

État du 2 novembre 2026. Ces essais précèdent la qualification native Windows de l’EXE ; les rapports Actions du commit livré restent la preuve de cette dernière.

## Moteurs et sources

`config/forensic-toolchain.json` épingle les 13 dépôts/projets EZ Tools, RegistryPlugins et Hayabusa 4.3.1. Les compilations ciblant `win-x64` ont réussi pour les 13 moteurs, y compris après désactivation des démarrages Exceptionless. Les 70 plugins RegistryPlugins compilent avec la version de contrat 2026.10.7 utilisée par RECmd. Ces compilations ont été exécutées avec le SDK .NET 10 sous Linux : elles ne constituent pas un lancement de l’EXE sous Windows.

## Essai réel du parcours

Les DLL managées produites pour EvtxECmd, AppCompatCacheParser et RECmd ont également été exécutées avec le runtime Linux de .NET 10, et Hayabusa avec son binaire Linux 4.3.1. Aucun moteur de cet essai n’est simulé.

- EVTX public DeepBlueCLI `disablestop-eventlog.evtx`, blob `5e7ce922ee681277c8c8d82413bb9ba944caef54` dans `Yamato-Security/hayabusa-sample-evtx` ; SHA-256 `7645e96c6d778f96d60ce2a6f209cc4202385c9d87cc077139921270a8e9bb23`.
- Ruche SYSTEM Windows 11 et LOG1/LOG2 publics du DFIR Artifact Museum, fournis compressés dans le dépôt RECmd à sa révision épinglée ; attribution et licence copiées dans le pack.
- EvtxECmd : 13 événements ; AppCompatCacheParser : 359 entrées ; RECmd batch Kroll : 5 228 paires clé/valeur et sorties des plugins.
- Fireblade : 16 bases d’analyse chargées dans une session, dont l’analyse des alertes.
- Hayabusa : deux détections, « Important Log File Cleared » et « Event Log Service Startup Type Changed To Disabled », avec références aux EVTX originaux.
- Empreintes de la ruche et de ses journaux vérifiées ; les journaux sont des compagnons et ne sont pas parsés comme des ruches autonomes.
- Essai répété avec les plugins au contrat épinglé et les moteurs sans télémétrie. Les métadonnées Git du dossier des règles ont été retirées comme dans le pack Windows ; la détection reste opérationnelle.

## Tests automatisés

La suite générale a exécuté 781 tests réussis, 25 ignorés et deux échecs de transparence des panneaux liés au nouveau conteneur d’onglets. Le fond du conteneur a ensuite été corrigé ; les quatre tests de rendu alpha, en modes clair et sombre, passent.

Les contrôles ciblés de la version corrigée couvrent le parsing, la création/reprise de session, les alertes simples et agrégées, la provenance de plusieurs EVTX, les sources modifiées, les sorties vides, le zéro explicite de détection, les moteurs absents, l’annulation d’un processus, les liens ignorés, les compagnons de registre, les archives traversant les chemins, les ressources d’aide et les panneaux transparents. Les tests de moteurs simulés servent aux erreurs et transitions d’état ; ils restent distincts de l’essai réel ci-dessus.

## Contrôles exigés dans l’EXE Windows

La construction compile les moteurs et plugins, embarque le runtime .NET, les règles et sources Hayabusa, les maps et le batch Kroll. Elle vérifie les points d’entrée des moteurs et les empreintes des archives. Le contrôle du fichier unique relocalisé exécute ensuite les moteurs intégrés, importe l’EVTX et la ruche d’exemple et exige au moins les deux alertes Hayabusa attendues, sans runtime .NET provenant du PATH du poste.

Les résultats ne qualifient pas chaque format ou variante pris en charge par les outils amont. Le parsing source, les limites de ressources des moteurs externes et la compatibilité Windows native doivent être distingués des garanties du moteur de grille DuckDB. La session garde son plafond de 1000 analyses et les fichiers refusés ou non chargés restent explicitement dans le bilan.

## Organisation des résultats

Le dialogue d’import propose un onglet par type d’artefact ou une analyse unique avec groupement sur l’artefact. Sur les 15 analyses de parsing de l’essai réel précédent, les deux organisations conservent exactement 7 627 lignes : trois onglets de familles dans le premier mode, une analyse regroupée dans le second. Les alertes Hayabusa restent indépendantes.

Les tests vérifient également les schémas hétérogènes, les noms de colonnes qui entrent en collision, les zéros initiaux, les fichiers sources, la reprise de session, l’annulation du choix et le maintien de la session originale si l’organisation échoue. Une disposition automatique d’un import précédent ne remplace pas le groupement choisi pour la collecte.

## Contexte des alertes Hayabusa

Le parcours réel a été répété avec l’organisation par artefact : trois analyses de parsing et une liste de deux alertes. Depuis « Important Log File Cleared », la commande de contexte retrouve une référence exacte et affiche les 13 événements EVTX dans la fenêtre de cinq minutes. Le fichier et EventRecordID identifient la référence ; les autres événements restent qualifiés de voisins temporels. L’essai passe dans l’interface Qt avec les bases réelles, sans simuler les parseurs ni Hayabusa.

Les tests couvrent également les identifiants identiques dans des fichiers ou machines distincts, les références agrégées et introuvables, les voisins provenant d’autres journaux de la même machine, les fenêtres et plafonds, la conservation des charges utiles et de la précision des dates, les entrées SQL hostiles, la reprise sans artefacts originaux et le lien vers les bases brutes après organisation des onglets. Le parcours graphique vérifie l’ouverture de la ligne source exacte et le retour aux alertes avec leurs filtres et annotations. La qualification Windows du fichier unique exige maintenant un contexte comportant une référence et des événements voisins.

## Matrice des 13 parseurs et affichage

Les moteurs épinglés ont été reconstruits avec .NET 10.0.403. Un second parcours réel vérifie chaque CSV produit, son import DuckDB et l’ouverture dans la grille Qt : nombre de lignes de la première page et égalité des valeurs de sa première ligne. Résultats locaux sous Linux :

| Parseur | Lignes importées | Affichage vérifié |
| --- | ---: | --- |
| EvtxECmd | 13 | oui |
| AmcacheParser | 2 | oui |
| AppCompatCacheParser | 359 | oui |
| PECmd | 2, réparties sur 2 sorties | oui |
| MFTECmd | 117 | oui |
| RECmd | 3720, sans plugins dans cet essai | oui |
| LECmd | 1 | oui |
| JLECmd | 1 | oui |
| WxTCmd | 151, réparties sur 2 sorties | oui |
| RBCmd | 1 | oui |
| RecentFileCacheParser | 6 | oui |
| SrumECmd | non qualifié sous Linux | moteur exigeant les bibliothèques ESE Windows |
| SQLECmd | non qualifié sous Linux | bibliothèque SQLite.Interop Windows |

Pour WxTCmd, la bibliothèque native SQLite Linux a été ajoutée uniquement au pack d’essai Linux. Le pack livré reste ciblé Windows. Une sortie vide d’un premier échantillon EVTX et JumpList n’a pas été comptée comme une réussite : l’essai a été répété sur des échantillons contenant des données.

`config/forensic-qa-fixtures.json` fixe les URL publiques et les empreintes SHA-256 des échantillons supplémentaires. Ils sont téléchargés et vérifiés pendant la construction, puis embarqués dans les ressources de qualification de l’EXE. L’EVTX et la ruche de qualification existants sont conservés. La qualification Windows exige désormais des résultats non vides de chacun des 13 parseurs, puis ouvre chaque analyse produite dans la grille et compare les valeurs affichées aux données importées. Elle échoue en cas de parseur absent, en erreur, sans sortie ou sans ligne. Son résultat n’est acquis qu’après réussite du workflow Windows.

Cette matrice vérifie des exemples représentatifs ; elle ne prouve pas toutes les versions Windows, tous les schémas SQLite, toutes les maps et tous les cas de corruption. Les formats non reconnus ou refusés restent dans le bilan de collecte.

## Relecture et régressions du contexte

Une nouvelle passe corrige la qualification d’une référence multiple lorsque le plafond ne conserve qu’un candidat : elle reste ambiguë. Le contexte signale également les voisins omis lorsque les références occupent toute la capacité. Les dates aux bornes du calendrier n’interrompent plus la création de la fenêtre ; une alerte d’une autre collecte ne peut pas emprunter les sources de la collecte active. L’ouverture du contexte passe par le parcours normal d’ouverture des analyses, qui traite les erreurs sans fermer prématurément l’analyse courante.

Les régressions couvrent aussi l’analyse source remplacée, l’annulation avant création et la conservation des filtres/notes au retour aux alertes. Les limites sont visibles dans le résumé même lorsque d’autres avertissements le précèdent ; les notes complètes restent dans son infobulle et dans la collecte.

Le parcours réel EvtxECmd + AmcacheParser + Hayabusa a été répété avec les deux organisations. Chacune produit deux alertes et un contexte de 13 événements avec une référence exacte ; les boutons ouvrent la ligne EVTX attendue puis reviennent à l’alerte. [Résultats](reports/20261102-real-context-organizations.json). Cet essai utilise les moteurs réels sous Linux, dont les DLL managées des parseurs ciblant Windows, et Qt hors écran.

## Résultats Windows de la première matrice complète

Le [workflow `323c980`](https://github.com/23R0534ZXT/fireblade/actions/runs/41409240830) a réussi 810 tests des sources sur chacune des versions Python Windows 3.11, 3.12 et 3.13, ainsi que les chemins UNC/longs et la matrice des lecteurs. Le contrôle de l’EXE a toutefois échoué : la nouvelle copie de SYSTEM dans le sous-dossier de matrice omettait LOG1/LOG2, nécessaires à cette ruche dirty. AppCompatCacheParser et RECmd l’ont refusée ; ce refus n’a pas été contourné. Le manifeste de fixtures inclut maintenant les deux compagnons avec leurs empreintes.

Le rapport de collecte produit par cet EXE contient néanmoins des sorties importées non vides pour les 13 moteurs sur les autres échantillons complets : notamment **309 lignes dans sept sorties SRUM**, **1042 lignes dans quatre sorties SQLECmd**, et **151 lignes dans deux sorties WxTCmd**. Les bases produites sous Windows ont toutes été rouvertes dans Qt hors écran sous Linux ; la première page de chaque sortie correspond aux valeurs de la base. Ce contrôle distingue parsing/import natifs Windows et rendu Qt Linux : il ne transforme pas le contrôle d’EXE échoué en qualification Windows réussie. [Rapport de ces imports et affichages](reports/20261102-native-parser-imports.json).

La relance Windows avec les compagnons doit encore réussir l’intégralité du contrôle et les qualifications suivantes avant publication. Les rapports du commit corrigé font foi.
