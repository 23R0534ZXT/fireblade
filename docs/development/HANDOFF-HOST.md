# Passation — portage Fireblade Host

20 novembre 2026, 15h50. Document de reprise : il décrit l'état exact du code, ce
qui est vérifié, ce qui est en cours, ce qui reste, l'environnement de travail et
les pièges déjà payés. Il doit suffire à reprendre sans rien redécouvrir.

---

## 1. Le but, et où il s'inscrit

Trois éditions sont visées :

- **Desktop** — l'exe Windows PySide6, publié (0.7.9), la référence fonctionnelle ;
- **Host** — la même application, conteneurisée, servie dans un navigateur, pour
  un analyste ou une petite équipe ;
- **Server** — multi-analystes, un process central qui pilote Docker, un
  conteneur par case, RBAC et journal d'audit.

Décision actée : dès que Host et Server couvrent le parcours métier complet,
**Desktop est gelé** et tout le développement continue sur les éditions Docker.
C'est pourquoi le portage Host est mené jusqu'au bout, écran par écran.

Le chantier en cours est **Host uniquement**. Server n'est pas commencé, et son
plan (architecture, phases, décisions) est dans `HANDOFF-DOCKER.md`.

---

## 2. État exact du code

| Quoi | Valeur |
| --- | --- |
| Branche | `feat/host-edition`, **40 commits** au-dessus de `main` |
| `main` | intacte, jamais poussée, rien de publié |
| Dernier commit | `faa2b49 Docs: hand over the Host port` |
| Porte complète | **verte** : `1752 passed, 28 skipped`, ruff propre, `TOUT EST VERT`, 17 min 23 s |
| Image | `fireblade:host`, ~890 Mo, saine sur `http://192.168.1.201:8095` |
| Cases ouverts sur le service | 8 |

---

## 3. Travail en cours, non commité, non vérifié

Une passe automatique a écrit le **backend de l'aperçu d'import** puis s'est
arrêtée avant de construire et de tester. Ce travail est **uniquement dans la
copie locale** `/root/fireblade-web` : ni sur la VM, ni dans git.

- `src/fireblade/web/service.py` — `preview_source(self, source: str | Path) -> dict`,
  vers la ligne 724 : lit les en-têtes d'un CSV, appelle
  `fireblade.core.profiles.detect_profile`, renvoie colonnes + profil + mapping.
- `src/fireblade/web/server.py` — `POST /api/cases/{identifier}/preview`
  (chemin serveur) et `POST /api/cases/{identifier}/preview-upload`
  (fichier envoyé par le navigateur), vers les lignes 115-140.

À faire, dans l'ordre : relire le code, le terminer, construire l'image,
appeler les deux routes sur un vrai fichier, comparer le profil renvoyé à ce que
donne `detect_profile` en ligne de commande, puis brancher l'interface (avant de
valider un import : colonnes, profil reconnu, mapping), et seulement ensuite
commiter. **Ne pas commiter en l'état, ne pas le présenter comme fait.**

---

## 4. Architecture du module web

Tout est dans `src/fireblade/web/`, quatre fichiers Python et trois fichiers
statiques, sans framework côté client :

| Fichier | Lignes | Rôle |
| --- | --- | --- |
| `service.py` | 1 372 | tout le métier : catalogue de cases, lecture des analyses, colonnes, filtres, tri, groupements, export, import, signets, notes, règles, vues, chronologie, IOC, détection, graphe, rapport, suivi, cycle de vie, archivage, disposition |
| `server.py` | 461 | FastAPI : **51 routes**, validation, traduction des erreurs en HTTP, fichiers statiques |
| `cli.py` | 99 | `serve` (le serveur) et `count` (compte les lignes d'un case — sert de test de fumée en conteneur) |
| `static/app.js` | 2 033 | client : grille, filtres, dialogues, onglets, rendu |
| `static/index.html` | 639 | structure de la fenêtre, calquée sur le desktop |
| `static/app.css` | 264 | palette et densité reprises de `ui/theme.py` |

Règle de conception : **le service ne réinvente rien**. Filtres, tris,
groupements, exports, rapports, destruction, chronologie, graphe, IOC, Hayabusa
sont des appels au noyau `fireblade.core`. Le web n'est qu'une façade HTTP sur du
code déjà testé par le desktop — c'est ce qui rend la parité crédible.

Le service n'écrit jamais les chemins enregistrés dans un case : un case créé
sous Windows garde ses `C:\…` et s'ouvre sous Linux par recherche du nom de
fichier dans le dossier du case (séparateurs normalisés).

---

## 5. Les routes, par groupe

- **Santé et catalogue** — `GET /health`, `GET /api/cases`, `GET /api/cases/{id}`,
  `POST /api/cases`, `POST /api/cases/import-package`, `GET …/package/download`,
  `POST …/package`, `POST …/archive`, `POST …/restore`, `POST …/destroy`.
- **Import** — `POST …/upload` (navigateur), `POST …/import` (chemin serveur),
  `GET …/imports` (historique par fichier), `POST …/preview` et
  `POST …/preview-upload` (en cours, non commités).
- **Lecture** — `GET …/analyses/{i}/rows` (pagination, recherche, tri simple et
  multiple, filtres, groupements, intervalle, `expression_json`, `bookmarks_only`),
  `GET …/columns`, `GET …/export` (CSV).
- **Confort d'analyse** — `bookmarks`, `bookmark`, `cellnotes`, `cellnote`,
  `rules`, `derived`, `views` (+ `views/{name}`), `display`.
- **Métier** — `…/timeline`, `…/search`, `…/ioc`, `…/hunts` (+ `/{name}`),
  `…/detect`, `…/graph` (avec `?navigator=true`), `…/report`,
  `…/reports/{name}`, `…/pivot`, `…/workspace`, `…/actions` (+
  `actions/export`).
- **Réglages** — `GET /api/profiles`, `GET /api/settings`.
- La racine `/` sert l'interface statique.

---

## 6. Ce qui est fait, onglet par onglet

Neuf onglets, comme le desktop.

**Analyses** — ouverture d'un case, choix de l'analyse, grille paginée.
Tri par colonne, tri multiple avec Maj, filtres par colonne avec opérateurs
(`contains`, `eq`, `ne`, `starts`, `ends`, `gt`, `ge`, `lt`, `le`, `empty`,
`not_empty`), filtre avancé ET/OU/NON (un groupe plat), groupement par colonne
avec descente dans un groupe, groupement d'une date par année / trimestre / mois /
semaine / jour / heure / minute / seconde, signets, notes de ligne, notes de
cellule (marquées d'un coin dans la grille), règles de coloration (dont création
depuis une cellule au clic droit), masquage / épinglage / redimensionnement des
colonnes, affichage booléen ✓/✗, colonnes dérivées, vues nommées, export CSV,
copie de ligne, affichage de la cellule entière, disposition enregistrée **dans
l'analyse** (pas dans le navigateur).

**Imports** — envoi par le navigateur, glisser-déposer, chemin serveur. Trois
dispositions : une grille par fichier, une grille par famille d'artéfacts
(défaut du desktop), une grille pour tout. Historique fichier par fichier avec
le lecteur utilisé et, en cas d'échec, la raison — c'est le comportement livré en
0.7.9 côté desktop, conservé ici.

**Cases** — création, renommage, destruction DoD 3 ou 7 passes avec certificat
écrit **hors** du dossier, archivage avec libération de l'espace, restauration,
export et import d'un case portable `.fireblade`.

**Chronologie** — construite par le `TimelineStore` du noyau, histogramme,
légende des sources, corrélation d'une entité, pagination.

**Chasse IOC** — collage d'indicateurs, analyse, résultats avec ligne, colonne et
règle appliquée. Chaque chasse laisse une trace dans le case
(`hunts/<horodatage>.json`) et se rejoue depuis « Saved hunts… ».

**Hayabusa + AI** — exécution de Hayabusa au niveau choisi, constats avec
tactiques, dédoublonnage par fichier. **Aucune IA n'est branchée** : l'onglet le
dit explicitement, il n'y a ni clé ni endpoint ni appel sortant.

**Actions & suivi** — actions avec responsable, priorité, statut ; clôture et
réouverture ; export.

**Attack graph** — construit par le noyau à partir des constats et des machines
déclarées, disposition calculée par le noyau, export d'une **couche MITRE ATT&CK
Navigator** (JSON officiel) et export **PNG** dessiné en double résolution.

**Détection EVTX** — le moteur du noyau, à travers le conteneur.

**Transverse** — recherche globale dans toutes les analyses, préférences avec
l'inventaire des lecteurs (13/13 + Hayabusa), réglages d'affichage (taille de
texte, hauteur de ligne, palette du desktop).

---

## 7. Le noyau, et la garantie qu'il reste réutilisable

`src/fireblade/core/` est la moitié précieuse du logiciel et ne doit jamais
dépendre de Qt. Deux garde-fous :

- `tests/core/test_no_qt.py` analyse les imports de chaque module de `core/` et
  échoue si l'un d'eux importe `PySide6` ou `fireblade.ui` ; il importe aussi
  tous les modules avec PySide6 bloqué.
- Un correctif a été nécessaire dans `core/layout_images.py` : les imports Qt sont
  passés à l'intérieur des deux fonctions qui en ont besoin.

Tests ajoutés pour le portage :

- `tests/core/test_no_qt.py` — la règle ci-dessus ;
- `tests/core/test_toolpack_host.py` — `dotnet.exe` sous Windows, `dotnet` sous
  Linux ;
- `tests/web/test_web_service.py` — construit un case comme le desktop, écrit un
  CSV, vérifie catalogue, lignes, filtres, export.

---

## 8. Docker

`Dockerfile` :

- base `python:3.12-slim` ;
- runtime **.NET 10** copié depuis `mcr.microsoft.com/dotnet/runtime:10.0`, avec
  `dotnet` lié dans `/usr/local/bin` ;
- les **treize lecteurs** Eric Zimmerman téléchargés au build par
  `scripts/fetch_readers.py` (~60 Mo), plus Hayabusa ;
- `libicu76` — sans elle, les outils .NET échouent sur
  `Couldn't find a valid ICU package` ;
- `chown` + `chmod -R a+rX /opt/fireblade/tools` : le service tourne en uid
  10001, sans ça chaque `.dll` répond `Permission denied` et le panneau des
  lecteurs n'en voit que trois ;
- utilisateur `fireblade` (uid 10001), `EXPOSE 8080`, `HEALTHCHECK` sur `/health`,
  `CMD python -m fireblade.web serve --root /data/cases --host 0.0.0.0 --port 8080 --tools /opt/fireblade/tools`.

`docker-compose.yml` : un service, port `${FIREBLADE_PORT:-8080}`, volume
`${FIREBLADE_CASES:-./cases}:/data/cases`, `TZ`, `restart: unless-stopped`. C'est
la future édition auto-hébergée, et la même image servira de conteneur de case
pour Server.

Les lecteurs tournent sous Linux via `ToolPack.dotnet(root)`, qui choisit
`dotnet.exe` sous Windows et `dotnet` sous Linux **sans changer la ligne de
commande** des outils. Vérifiés réellement : EvtxECmd (1 327 lignes sur
`System.evtx`, CSV identique à Windows), PECmd (316 fichiers, 1 046 lignes),
AppCompatCacheParser (239), LECmd (2), JLECmd (8). Non encore validés en sortie
réelle : MFT, SRUM, corbeille, Amcache ; WxTCmd, SQLECmd et RECmd ont d'abord
échoué sur des options de ligne de commande inventées — la règle est de laisser
`core/collection.py` construire les commandes, pas de les taper à la main.

---

## 9. Environnement de travail

- **Copie locale** : `/root/fireblade-web` — ce n'est **pas** un dépôt git, c'est
  un miroir synchronisé par `scp` vers la VM. Le vrai git est sur la VM.
- **Dépôt** : `fb@192.168.1.80`, `C:/Users/fb/dev/fireblade`, git dans
  `C:/Users/fb/tools/git/cmd/git.exe`.
- **Porte complète** : sur la VM,
  `.\.venv\Scripts\python.exe -m scripts.dev_check`, ~17 min, doit finir par
  `TOUT EST VERT`. À lancer en tâche de fond.
- **Docker** : `root@192.168.1.201`, image `fireblade:host`, conteneur
  `fireblade-host`, port `8095:8080`, volume `/srv/fbcases:/data/cases`.
- **Cases de test** : `e3253c49ca6848458e28d07642fa9423` (démo, 480 lignes, 8
  colonnes), `2a7afd0b938e4f53a9be2018bab5e16b` (EVTX, 1 327 lignes, 31
  colonnes), `3993410bbd4d45338f932f4554afaa93` (Security.evtx, pivot processus).

Boucle de build (un build prend 4 à 5 minutes : le lancer en tâche de fond et
travailler pendant ce temps) :

```
cp -r /root/fireblade-web/src/fireblade/web /root/fbctx/src/fireblade/
tar czf /tmp/fbctx.tgz -C /root/fbctx .
scp /tmp/fbctx.tgz root@192.168.1.201:/root/
ssh root@192.168.1.201 'rm -rf /opt/fireblade-build && mkdir -p /opt/fireblade-build &&
  tar xzf /root/fbctx.tgz -C /opt/fireblade-build &&
  docker build -q -t fireblade:host /opt/fireblade-build &&
  docker rm -f fireblade-host; sleep 2;
  docker run -d --name fireblade-host -p 8095:8080 -v /srv/fbcases:/data/cases fireblade:host'
curl -s http://192.168.1.201:8095/health
```

Puis vérifier la route touchée, pas seulement `/health`.

---

## 10. Comment on prouve qu'une chose marche

Deux voies, jamais une seule :

1. **appel API réel** — `curl` sur la route, avec un case de test, et on lit la
   réponse (nombre de lignes, total, colonnes) ;
2. **navigateur réel** — clic, capture d'écran, et on regarde l'image.

Un `docker build` réussi ne prouve rien : il ne dit pas que le conteneur sert le
bon code. Un test unitaire vert ne prouve pas qu'un bouton existe. Un commit ne
se fait qu'après l'une des deux voies, et le message dit ce qui a été vérifié.

---

## 11. Ce qui reste

1. **Aperçu d'import** (§3) — finir, construire, vérifier, brancher l'interface.
2. **Groupes de filtres imbriqués** — le dialogue écrit un groupe plat ; le noyau
   (`FilterGroup`) accepte des arbres plus profonds. Purement de l'interface.
3. **Revue de `HOST-PARITY.md`** groupe par groupe : cocher ce qui est couvert,
   traiter ce qui reste utile, déclarer le reste.
4. **Porte complète**, puis documentation (`HOST-EDITION.md`, `HOST-PARITY.md`,
   `RELEASE-NOTES.md`) et préparation du lot.
5. Ne pas oublier que **Windows reste la référence publiée** : aucune régression
   acceptée, la porte complète avant chaque publication.

---

## 12. Hors périmètre, à déclarer et non à coder

- **Explorateur Windows** — « Afficher dans l'Explorateur », ouvrir le dossier
  parent : il n'y a pas d'explorateur système derrière un navigateur, et les
  dossiers du serveur ne sont pas ceux de l'analyste.
- **Gestion de fenêtres** — détacher un panneau, dispositions de fenêtres, barres
  d'outils flottantes. Le web obtient le même résultat par les dialogues Group…
  et Columns….
- **L'IA** — rien de branché. La décision (modèle local dans le conteneur ou API
  distante) appartient à l'utilisateur et détermine ce qui peut sortir du
  serveur. C'est aussi une des décisions ouvertes de Server.
- **Forcer un profil CSV à l'import** — `detect_profile` vit dans la mise en page
  automatique et les préférences ; il n'existe aucun paramètre de forçage dans le
  chemin d'import, même côté desktop. Le faire demanderait une évolution du
  noyau, donc des deux éditions : à décider, pas à improviser.

---

## 13. Décisions en attente

- **IA** : dans le conteneur de case (accès réseau sortant) ou dans le service
  central (le contenu transite) ? Choix de confidentialité autant que technique.
- **Profils CSV** : ajouter un forçage dans le noyau, ou s'en tenir à la
  détection ?
- **Server** (à venir) : chiffrement par case dès la phase 2, un conteneur par
  case, trois rôles RBAC + affectation par case, SQLite de contrôle au départ.
  Tout cela est argumenté dans `HANDOFF-DOCKER.md`.

---

## 14. Les 40 commits, dans l'ordre

```
f508334 Host edition: the core served over HTTP, first grid
94b9e40 Host: align the column filter row; slim the image
d0d3b61 Docs: EvtxECmd produces the same CSV under Linux
4d26660 Linux readers: one .NET host branch, measured on real artifacts
243ba5c Host: import over the core collection, and a countable parity checklist
77dea73 Host: import a real artifact inside the container
8e0c7f8 Host: import from the browser
d8544ee Host: bookmarks and notes in the grid
2d1d9a1 Host: grouping with drill-down
6e1acba Host: filter operators, multi-column sort, column manager
eda725b Host: the timeline, built by the core's TimelineStore
6a22891 Host: IOC hunting
cbee09a Host: the client report
47c7923 Host: create, rename and destroy a case
a87c132 Host: actions and tracking
a313ed1 Host: global search across the case
67c3f4d Host: the import history, file by file
352c0c3 Host: derived columns, column resizing, real toolbar icons
df42d50 Host: "what launched this process?"
7b5432e Host: colour rules
2df5b63 Host: the detection engine runs in the container
5f201f4 Host: the attack graph
23d8d37 Host: EVTX detection tab
cc98f5a Host: named views
9743a4d Host: cell notes
aa32633 Host: cell notes
f67901b Host: the portable case
1ea606f Host: preferences, and a tool pack that cannot be built half-empty
6b8e082 Host: the tool pack belongs to the service user
c8dd921 Host: group a date column by day, month, year…
472c829 Host: the import layout, and a gate that stays green
ce12bb9 Host: archive and restore
3446858 Host: boolean columns and row height
ea5019d Host: row actions and the ATT&CK layer
65d1d4f Host: the advanced filter, as a FilterGroup
2c46aca Docs: the parity checklist, with what is covered and what is not
4314305 Host: hunts leave a record
3e2434a Host: the column layout belongs to the analysis
f1d95d4 Host: the graph as a PNG
faa2b49 Docs: hand over the Host port
```

---

## 15. Pièges déjà payés

- **LF / CRLF** : les fichiers édités depuis Linux arrivent en LF, git prévient
  qu'il les convertira ; c'est normal, ne rien « corriger ».
- **Un build réussi ne prouve rien** : toujours rappeler la route touchée après
  redémarrage du conteneur.
- **Chemins Windows** : une session enregistrée par le desktop contient
  `C:\…` ; le service essaie le chemin enregistré, puis cherche le fichier par
  son nom dans le dossier du case, sans jamais réécrire la session.
- **Archiver** un case qui contient encore des preuves originales est **refusé**
  par le noyau (c'est voulu) ; **restaurer** crée un **nouveau** case, l'archive
  restant la copie conservée et le dossier vidé l'entrée de catalogue.
- **Certificat de destruction** : le générateur écrit du HTML sauf cible `.pdf` ;
  l'écrire en `.html`, hors du dossier du case.
- **Pivot** : refuser un jeton JSON (bruit EvtxECmd dans `PayloadData`) et
  retomber sur un chemin d'exécutable trouvé dans n'importe quelle cellule. Une
  ligne ne « nomme » un processus que si elle en donne un.
- **`findstr` sous Windows** ramène aussi les tests quand on cherche un libellé
  d'interface : la colonne « declared in » de `PARITY.md` donne le module
  d'origine, c'est plus court.
- **VM Windows** : elle tombe si VT-x n'est pas actif dans le BIOS ; vérifier
  `grep -c vmx /proc/cpuinfo` sur le nœud avant de conclure à une panne réseau.
- **Outils .NET** : ne jamais taper la ligne de commande à la main, laisser
  `core/collection.py` la construire (RECmd exige un switch explicite, WxTCmd et
  SQLECmd n'ont pas la même grammaire).

---

## 16. Par où commencer, concrètement

1. Lire §2 et §3, puis `git log --oneline -5` et `git status` sur la VM : savoir
   si le travail non commité est toujours là.
2. Terminer l'aperçu d'import, construire, appeler les deux routes sur un vrai
   CSV, vérifier le profil, brancher l'interface, commiter.
3. Faire les groupes de filtres imbriqués, vérifier, commiter.
4. Reprendre `HOST-PARITY.md`, cocher, traiter le reste utile.
5. Lancer la porte complète, mettre à jour les documents, préparer le lot — et
   ne pousser sur `main` que sur demande explicite de l'utilisateur.
