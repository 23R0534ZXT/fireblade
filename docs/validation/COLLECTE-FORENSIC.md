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
