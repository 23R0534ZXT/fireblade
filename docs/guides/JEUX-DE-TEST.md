# Quel jeu de test choisir ?

## Découvrir les formats : pack v1

[Fireblade-Test-Pack-v1.zip](https://github.com/23R0534ZXT/fireblade/releases/download/test-pack-v1/Fireblade-Test-Pack-v1.zip) est un **pack de découverte représentatif**, pas une collecte complète de poste.

Le ZIP publié contient **49 fichiers**, pèse **5 118 829 octets** (environ 5,1 Mo) et occupe **60 599 291 octets** après extraction (environ 60,6 Mo), avant décompression éventuelle des archives CatScale et création des analyses. Les bases d’analyse et les sorties des parseurs occupent de l’espace supplémentaire. Les fichiers compressibles, notamment certaines bases d’exemple, expliquent la différence entre la taille du ZIP et la taille extraite.

| Contenu | Portée |
|---|---|
| 14 fichiers natifs dans la collecte Windows principale | Exemples pour les 13 EZ Tools et leurs fichiers compagnons ; chaque variante de chaque artefact n’est pas représentée |
| 1 ruche Shellbags | 523 entrées décodées attendues ; ruche sale sans ses journaux, avertissement attendu |
| 1 base WebCache ESE | 1 612 lignes attendues, métadonnées comprises |
| EVTX de l’exercice | 13 événements, au moins deux détections Hayabusa attendues |
| CatScale extrait et archive équivalente | 26 lignes chacune, sept familles ; contenu synthétique |
| CatScale de volume | Chronologie synthétique de 100 000 lignes dans une archive compressée |
| Exports CSV, TSV et XLSX | Six lignes chacun, avec Unicode, identifiants exacts et textes multilignes |

Les artefacts Windows viennent de collections publiques indépendantes. Ils ne constituent pas un même incident, et ce pack ne promet pas de fournir « tous les artefacts » d’un système. Les sources, licences, empreintes et résultats attendus sont inclus dans le ZIP.

L’empreinte SHA-256 du ZIP v1 publié est `a546e3eac159f6e9a9e9c90360f4f89bec5d9bd1ebe7d86bf7fc23a6d2dccb9f`. Sa validation d’origine utilise le commit qualifié `0c36f0d` ; cette provenance historique n’est pas réécrite lorsque le workflow est mis à jour pour les futurs candidats.

## Tester le volume : CSV de plus de 3 Gio

[Le jeu de charge séparé](TESTER-3GIB.md) contient **2 441 216 enregistrements, 18 colonnes et 3 222 648 632 octets de CSV**. Il sert à vérifier l’import, la pagination, les tris, les groupes, les filtres et les exports sur un grand tableau.

C’est un CSV synthétique. Il ne remplace pas les fichiers natifs d’une collecte et ne prouve pas la couverture de tous les parseurs ou le comportement sur une enquête réelle.

## Tester une investigation réaliste

Une collecte réelle peut atteindre plusieurs gigaoctets, voire davantage : journaux longs, MFT, registres, historiques de navigateurs, nombreuses traces d’activité et plusieurs hôtes. Sa taille dépend des données collectées ; elle ne mesure pas à elle seule la qualité d’un test.

Le dépôt ne fournit actuellement **aucun gros dossier cohérent réunissant tous ces artefacts autour d’un incident**. Pour ce type d’exercice, il faut un jeu public redistribuable avec un scénario, sa chronologie, sa provenance et des résultats de référence. Dupliquer les petits fichiers jusqu’à atteindre plusieurs gigaoctets fournirait un test de volume, sans constituer une nouvelle couverture forensic.

Pour un premier retour sur Fireblade, commencer par le petit pack. Pour un retour de performance, utiliser le jeu de charge en indiquant la machine, la version de Fireblade et les opérations mesurées.
