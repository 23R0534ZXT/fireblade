# Grand pack brut Fireblade — exercice de parsing

Ce pack est destiné à **importer et parser des fichiers bruts**, pas à ouvrir des CSV déjà calculés. Il vise au moins **3 Gio de données d’entrée après extraction**. La taille du ZIP est différente et peut être nettement inférieure, notamment pour les journaux texte et les zones compressibles des artefacts natifs.

## Ce que contient le pack

- `01-Windows` : artefacts natifs publics issus de DFIRArtifactMuseum, conservés sans réécriture et séparés par plateforme, origine et famille : MFT, USN, ruches et journaux de registre, EVTX, Prefetch, LNK, Jump Lists, SRUM, Amcache, Windows Timeline et RecentFileCache. Les fichiers `.7z` des sources sont extraits par le générateur : ils ne sont pas laissés comme archives à faire parser.
- `01-Windows/Reference-Readers` : les petits artefacts Windows du pack de découverte, dont les références WebCache et Shellbags. Ce groupe couvre les exemples des lecteurs ; il ne sert pas à gonfler la taille du pack.
- `02-Linux-CatScale` : quatre hôtes de laboratoire **synthétiques**, avec journaux auth, syslog et audit en texte original, processus, connexions, historique et persistance dans des chemins de collecte CatScale. Aucun CSV d’analyse n’est fourni dans ce groupe.
- `MANIFEST.json` : taille et SHA-256 de chaque fichier, type de provenance et total des données brutes.
- `SOURCES.json`, `NOTICES` : références publiques épinglées, empreintes, licences et omissions du générateur.
- `SCENARIO-LINUX.json` : scénario, indicateurs attendus, nombre de lignes et emplacements des événements injectés.
- `validation-windows.json` et `RESULTATS-ATTENDUS.md`, lorsqu’ils accompagnent la release : résultats de parsing mesurés sous Windows pour cette archive.

Les collections Windows proviennent de laboratoires publics distincts. Leurs horloges, comptes et traces ne forment **pas un seul incident**. Conserver cette séparation lors de l’enquête ; ne pas inventer une relation entre deux sources parce qu’elles sont distribuées dans le même ZIP. Le scénario Linux est un exercice séparé, généré et explicitement identifié comme tel.

## Premier parcours Windows

1. Télécharger l’EXE Fireblade indiqué par la release et vérifier son SHA-256.
2. Extraire le ZIP dans un dossier disposant de suffisamment d’espace. Les analyses, CSV produits par les parseurs et fichiers temporaires s’ajoutent à la taille brute du pack. Commencer avec un sous-dossier d’origine si l’espace disque est limité.
3. Créer un dossier d’enquête **Windows**, puis utiliser **Importer un dossier de collecte…** sur un groupe de `01-Windows`. Choisir d’abord **un onglet par fichier** pour observer les résultats individuels.
4. Examiner **Collecte et détection** : fichiers reconnus, lecteurs exécutés, avertissements et éventuels résultats partiels. Les journaux de registre restent à côté de leurs ruches.
5. Pour les sous-dossiers EVTX, lancer Hayabusa puis ouvrir le contexte d’une alerte et l’événement source. Les détections dépendent de la collection et de la version des règles ; le rapport de validation ne garantit pas un verdict sur chaque alerte.
6. Comparer les traces MFT, registre, Prefetch et raccourcis d’une même origine. Conserver les références de source, les notes et les limites constatées.

Les artefacts publics peuvent présenter des états sales, des variantes ou des traces anciennes. Les avertissements font partie du résultat à examiner ; aucun résultat vide ou refus de lecteur ne doit être transformé en réussite silencieuse.

## Scénario Linux : retrouver une connexion et une persistance

1. Créer un dossier d’enquête distinct, puis importer le dossier `catscale_out` d’un des hôtes `lab-edge-01` à `lab-edge-04`.
2. Retrouver l’adresse de documentation **198.51.100.42** et l’utilisateur **backup** dans les journaux auth. Un échec est suivi d’une connexion acceptée.
3. Chercher **/usr/bin/curl**, **/etc/cron.d/ops-sync**, **ops-sync.service** et **updates.example.test** dans audit, syslog, les processus, l’historique et la crontab.
4. Construire une chronologie en tenant compte des formats de date : les journaux auth/syslog sont en ISO UTC, les événements audit gardent leur timestamp Unix source.
5. Ajouter des notes, sauvegarder puis rouvrir le dossier et produire un rapport. Expliquer les rapprochements et ce que les traces ne permettent pas de conclure.

Les adresses des réseaux 192.0.2.0/24 et 198.51.100.0/24 et le domaine `.test` sont réservés à la documentation. Le texte du scénario n’est pas exécuté et aucune connexion vers ces indicateurs n’est nécessaire au test.

## Résultats attendus et volume

Les comptes exacts sont dans le manifeste et le rapport joints à la release. Les journaux de fond contiennent des événements distincts : timestamps, sessions, PID, chemins et utilisateurs varient. Le générateur ne duplique pas un petit fichier jusqu’à atteindre une taille cible et n’ajoute pas de remplissage aléatoire.

Le volume Windows résulte des artefacts publics originaux. Le volume Linux résulte de véritables lignes de journaux bruts synthétiques. Ce corpus n’est ni une image disque, ni une acquisition réelle unique, ni une preuve que tous les formats possibles sont pris en charge.
