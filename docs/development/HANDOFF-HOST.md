# Passation — portage Fireblade Host

20 novembre 2026, 17 h 20. Document de reprise : il décrit l'état exact du code, ce
qui est vérifié, ce qui reste, l'environnement de travail et les pièges déjà payés.
Il doit suffire à reprendre sans rien redécouvrir.

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
C'est pourquoi le portage Host est mené jusqu'au bout, commande par commande.

Le chantier en cours est **Host uniquement**. Server n'est pas commencé, et son
plan (architecture, phases, décisions) est dans `HANDOFF-DOCKER.md`.

---

## 2. État exact du code

| Quoi | Valeur |
| --- | --- |
| Branche | `feat/host-edition`, **46 commits** au-dessus de `main` |
| `main` | intacte, jamais poussée, rien de publié |
| Dernier commit | `9ba585f Host: the grouped chart, and columns frozen on either edge` |
| Arbre de travail | propre — les trois documents non suivis sont hors sujet |
| Porte complète | **verte** : `1789 passed, 28 skipped`, ruff propre, `TOUT EST VERT`, 16 min 52 s |
| Tests web | **42**, dont 6 de parité qui refusent une couverture sans test |
| Image | `fireblade:host`, saine sur `http://192.168.1.201:8095` |
| Cases ouverts sur le service | 8, plus `poste-fr.csv` importé pour la recette d'encodage |

La commande qui répond à « est-ce que tout tient encore » :

```
.\.venv\Scripts\python.exe -m scripts.dev_check
```

---

## 3. Ce qui a été livré dans cette passation

Trois commits, chacun vérifié par un appel réel **et** un passage navigateur :

1. **`6dda2f8` L'aperçu d'import** — `preview_source()` dans `service.py`, deux
   routes (`POST …/preview` chemin serveur, `POST …/preview-upload` fichier
   envoyé), et le dialogue : colonnes avec leur rôle, profil reconnu par
   `detect_profile`, mapping (tri, horodatages, booléens, colonnes dérivées,
   règles de couleur), échantillon de lignes, taille, délimiteur, encodage.
   Rien n'est copié, haché ni écrit par l'aperçu.
2. **`19aaae4` Les options CSV, la sélection, le menu de ligne** —
   - le dialogue d'import offre **séparateur et encodage** comme le desktop
     (`automatic`, utf-8, utf-16, utf-32, cp1252, latin-1) ; changer l'un relit
     l'aperçu, et l'import lit le fichier avec ce choix ;
   - **sélection** de lignes (Maj = intervalle, Ctrl = ajout), et les actions
     portent sur la sélection : copier, marquer, noter ;
   - **menu contextuel** de cellule complet : valeur, ligne, filtre, exclusion,
     tri croissant/décroissant, groupement, épinglage, masquage, note, règle ;
   - deux défauts corrigés au passage : un import **remplaçait** la session
     (les analyses précédentes disparaissaient), et le champ de filtre perdait
     l'opérateur dès qu'on le rééditait (`= x` redevenait `contains x`).
3. **`8f95801` La parité comptée** — `host-parity.json` classe les 157 libellés
   que le desktop expose (104 commandes, 40 valeurs de paramètre, 13 menus) ;
   `scripts/host_parity_report.py` en génère `HOST-PARITY.md` ; six tests
   refusent une couverture sans test nommé, un « déclaré » sans raison, un
   « à faire » sans plan, ou une page qui ne correspond plus à la carte. Plus
   `tests/web/test_web_routes.py` : **17 tests** qui exercent chaque groupe de
   routes sur un vrai case.

---

## 4. La parité, et comment elle se lit

`docs/development/HOST-PARITY.md` est **généré**, jamais écrit à la main :

```
python scripts/host_parity_report.py           # régénère la page
python scripts/host_parity_report.py --check    # échoue si la page a dérivé
```

Trois statuts, et un seul est une promesse :

- **covered** — le navigateur le fait, *et* un test nommé l'exerce. Le test de
  parité vérifie que ce test existe vraiment (`ast` sur `tests/`).
- **declared** — impossible ou hors sujet derrière un navigateur, avec la raison
  (pas d'explorateur système, pas de gestion de fenêtres, pas d'IA branchée).
- **todo** — vraie commande du desktop non portée, avec son plan. **14 restent.**

État actuel : 104 commandes ⇒ 74 couvertes, 16 déclarées hors périmètre, 14 à faire.

---

## 5. Architecture du module web

Tout est dans `src/fireblade/web/`, quatre fichiers Python et trois fichiers
statiques, sans framework côté client :

| Fichier | Lignes | Rôle |
| --- | --- | --- |
| `service.py` | ~1 450 | tout le métier, façade sur `fireblade.core` |
| `server.py` | ~470 | FastAPI : 52 routes, validation, erreurs HTTP, statique |
| `cli.py` | 99 | `serve` et `count` |
| `static/app.js` | ~2 350 | client : grille, filtres, dialogues, onglets |
| `static/index.html` | ~650 | structure de la fenêtre, calquée sur le desktop |
| `static/app.css` | ~265 | palette et densité reprises de `ui/theme.py` |

Règle de conception inchangée : **le service ne réinvente rien**. Filtres, tris,
groupements, exports, rapports, destruction, chronologie, graphe, IOC, Hayabusa
sont des appels au noyau. Le web n'est qu'une façade HTTP sur du code déjà testé
par le desktop — c'est ce qui rend la parité crédible.

Le service n'écrit jamais les chemins enregistrés dans un case : un case créé
sous Windows garde ses `C:\…` et s'ouvre sous Linux par recherche du nom de
fichier dans le dossier du case (séparateurs normalisés).

---

## 6. Ce qui est fait, onglet par onglet

**Analyses** — ouverture, choix de l'analyse, grille paginée. Tri simple et
multiple (Maj), filtres par colonne avec opérateurs et préfixe visible, filtre
avancé ET/OU/NON **imbriqué** (profondeur 3), groupement avec descente dans un
groupe, groupement d'une date par année → seconde, signets, notes de ligne, notes
de cellule, **sélection multiple** et ses actions, règles de couleur (dont depuis
une cellule), colonnes masquées / épinglées / redimensionnées, booléens ✓/✗,
colonnes dérivées, vues nommées, export CSV, copie, cellule entière, disposition
enregistrée dans l'analyse. **Fermeture d'une analyse** depuis l'onglet (le
fichier reste dans le case).

**Imports** — envoi navigateur, glisser-déposer, chemin serveur, **aperçu avant
lecture** avec **séparateur et encodage réglables**, trois dispositions, historique
fichier par fichier avec le lecteur et la raison d'un échec.

**Cases** — création, renommage, destruction DoD avec certificat hors du dossier,
archivage, restauration, export/import d'un case portable `.fireblade`.

**Chronologie** — `TimelineStore` du noyau, histogramme, légende des sources,
corrélation d'une entité, pagination.

**Chasse IOC** — collage, analyse, résultats (ligne, colonne, règle) ; chaque
chasse laisse `hunts/<horodatage>.json` et se rejoue.

**Hayabusa + AI** — exécution au niveau choisi, constats avec tactiques,
dédoublonnage par fichier. **Aucune IA branchée**, l'onglet le dit.

**Actions & suivi** — création, modification, clôture, export CSV.

**Attack graph** — construit par le noyau, couche MITRE ATT&CK Navigator, PNG.

**Détection EVTX** — moteur du noyau, à travers le conteneur.

**Transverse** — recherche globale, préférences (runtime, lecteurs, profils),
réglages d'affichage.

---

## 7. Le noyau, et ce qu'on y a touché

`src/fireblade/core/` ne doit jamais dépendre de Qt : `tests/core/test_no_qt.py`
le vérifie module par module.

Cette passation a modifié **une seule** fonction du noyau : `Collection.__init__`
accepte désormais `delimiter=None, encoding='auto'` et les transmet à
`Case.import_csv` sur le chemin CSV natif. Les valeurs par défaut reproduisent
exactement l'ancien comportement (détection automatique), donc le desktop est
inchangé ; 37 tests de collection ont été relancés verts.

---

## 8. Docker

`Dockerfile` : `python:3.12-slim`, runtime .NET 10, les treize lecteurs Eric
Zimmerman + Hayabusa au build, `libicu76`, `chmod -R a+rX` sur les outils,
utilisateur uid 10001, `HEALTHCHECK` sur `/health`.

`docker-compose.yml` : un service, port `${FIREBLADE_PORT:-8080}`, volume
`${FIREBLADE_CASES:-./cases}:/data/cases`, `restart: unless-stopped`. C'est la
future édition auto-hébergée, et la même image servira de conteneur de case pour
Server.

Lecteurs validés en sortie réelle : EvtxECmd (CSV identique à Windows), PECmd,
AppCompatCacheParser, LECmd, JLECmd. Non encore validés : MFT, SRUM, corbeille,
Amcache (WxTCmd, SQLECmd, RECmd exigent que `core/collection.py` construise la
ligne de commande — ne jamais la taper à la main).

**Piège de build** : le contexte `/root/fbctx` est un miroir ; il doit contenir
aussi la version courante de `core/collection.py`. `/root/build_host.sh` le
récupère par `scp` à chaque build, en plus du dossier `web`.

---

## 9. Environnement de travail

- **Copie locale** : `/root/fireblade-web` — miroir de travail (web, tests, docs),
  ce n'est **pas** un dépôt git. Le vrai git est sur la VM.
- **Dépôt** : `fb@192.168.1.80`, `C:/Users/fb/dev/fireblade`, git dans
  `C:/Users/fb/tools/git/cmd/git.exe`.
- **Porte complète** : sur la VM,
  `.\\.venv\\Scripts\\python.exe -m scripts.dev_check`, ~17 min.
- **Docker** : `root@192.168.1.201`, image `fireblade:host`, conteneur
  `fireblade-host`, port `8095:8080`, volume `/srv/fbcases:/data/cases`.
- **Cases de test** : `e3253c49ca6848458e28d07642fa9423` (démo),
  `2a7afd0b938e4f53a9be2018bab5e16b` (EVTX, 1 327 lignes),
  `3993410bbd4d45338f932f4554afaa93` (Security.evtx 31 574 lignes + pivot).
- **Build** : `/root/build_host.sh` (copie `web` + `collection.py`, tar, scp,
  `docker build`, redémarrage, attente de `/health`). 4 à 5 minutes.

Après un build, **appeler la route touchée**, pas seulement `/health`.

---

## 10. Comment on prouve qu'une chose marche

Deux voies, jamais une seule :

1. **appel API réel** — `curl` sur la route, avec un case de test, et on lit la
   réponse (nombre de lignes, total, colonnes) ;
2. **navigateur réel** — clic, capture, et on regarde l'image.

Un `docker build` réussi ne prouve rien. Un test unitaire vert ne prouve pas
qu'un bouton existe. Un commit ne se fait qu'après l'une des deux voies, et le
message dit ce qui a été vérifié.

Troisième garde-fou, ajouté cette fois : **une couverture de parité doit nommer
un test qui existe**, sinon `tests/web/test_host_parity.py` échoue.

---

## 11. Ce qui reste, dans l'ordre du fichier de parité

Quatorze commandes, toutes listées avec leur plan dans `HOST-PARITY.md` :

1. **Chronologie, mode de date** (3 commandes) — même colonne, colonnes séparées,
   sans date. Le panneau choisit aujourd'hui la colonne tout seul.
2. **Hayabusa** (3) — marquer toutes les alertes d'un constat, ouvrir les alertes
   filtrées dans la grille, exporter les sources.
3. **Panneau de compatibilité** (3 + Plugins) — profils, sessions, en-têtes
   Timeline Explorer, inventaire des plugins.
4. **Graphe** (2) — nœud libre, contexte EVTX d'une alerte.
5. **Palette personnalisée** (1) — les deux thèmes du desktop, pas de couleurs libres.

---

## 12. Hors périmètre, à déclarer et non à coder

- **Explorateur Windows**, ouvrir le dossier parent, « Ouvrir avec… » : il n'y a
  pas d'explorateur système derrière un navigateur.
- **Gestion de fenêtres** — détacher un panneau, dispositions de fenêtres, barres
  d'outils, position de l'arbre et des détails : c'est du chrome de bureau.
- **Animation au démarrage** — un onglet de navigateur n'a pas d'ident.
- **L'IA** — rien de branché, décision ouverte (modèle local dans le conteneur ou
  API distante) ; elle détermine ce qui peut sortir du serveur.

---

## 13. Décisions en attente

- **IA** : dans le conteneur de case (accès réseau sortant) ou dans le service
  central (le contenu transite) ?
- **Profils CSV** : ajouter un forçage dans le noyau, ou s'en tenir à la
  détection ? (L'aperçu montre le profil, il ne le force pas encore.)
- **Server** (à venir) : chiffrement par case, un conteneur par case, trois rôles
  RBAC, SQLite de contrôle — argumenté dans `HANDOFF-DOCKER.md`.

---

## 14. Les derniers commits

```
9ba585f Host: the grouped chart, and columns frozen on either edge
d774248 Docs: the Host handover, at 72 of 104 commands
8f95801 Host: parity counted, and the surface proven group by group
19aaae4 Host: the CSV options, a selection, and the desktop row menu
6dda2f8 Host: preview an import before anything is read
12903fc Docs: the handover, in full
faa2b49 Docs: hand over the Host port
f1d95d4 Host: the graph as a PNG
3e2434a Host: the column layout belongs to the analysis
4314305 Host: hunts leave a record
```

`git log --oneline main..HEAD` donne les 46.

---

## 15. Pièges déjà payés

- **Le shell SSH de la VM est PowerShell 5.1** : `&&` n'y existe pas. Chaîner
  avec `;`, ou mettre la commande dans un `.ps1`.
- **Un `ssh` coupé par le timeout de l'outil ne tue pas la commande distante.**
  La porte a continué et a fini verte ; avant de relancer, lire le journal
  (`C:\Users\fb\devcheck.log`) et compter les `python.exe`. Ne jamais lancer une
  deuxième suite pendant ce temps : DuckDB verrouille.
- **`cmd /c "… > log 2>&1"`** est la bonne redirection pour la porte ; un pipe
  PowerShell transforme les avertissements Qt de stderr en erreurs.
- **LF / CRLF** : les fichiers édités depuis Linux arrivent en LF, git prévient
  qu'il les convertira ; c'est normal, ne rien « corriger ».
- **Un build réussi ne prouve rien** : rappeler la route touchée après
  redémarrage du conteneur.
- **Le contexte de build doit suivre le noyau** : `collection.py` a changé, et un
  `fbctx` périmé construit une image qui ignore le changement.
- **Un import ne doit jamais remplacer la session** : `InvestigationLibrary.save`
  écrit la liste qu'on lui donne. Le service relit la session précédente et
  concatène, sinon la deuxième importation efface la première.
- **Le champ de filtre doit afficher l'opérateur** : sans préfixe, une valeur
  filtrée avec `=` redevenait `contains` à la première réédition.
- **Un `mark` sans note n'existe pas** : `case.bookmark(row, None)` supprime la
  marque. Toute action « marquer » doit écrire un texte.
- **Chemins Windows** : une session enregistrée par le desktop contient `C:\…` ;
  le service essaie le chemin enregistré, puis cherche le fichier par son nom.
- **Archiver** un case qui contient encore des preuves originales est **refusé**
  par le noyau (voulu) ; **restaurer** crée un **nouveau** case.
- **Certificat de destruction** : le générateur écrit du HTML sauf cible `.pdf` ;
  l'écrire en `.html`, hors du dossier du case.
- **Pivot** : refuser un jeton JSON (bruit EvtxECmd) et retomber sur un chemin
  d'exécutable trouvé dans n'importe quelle cellule.
- **Outils .NET** : ne jamais taper la ligne de commande à la main, laisser
  `core/collection.py` la construire.
- **`findstr` sous Windows** ramène aussi les tests quand on cherche un libellé
  d'interface : la colonne « declared in » de `PARITY.md` (`scripts/parity_inventory.py`)
  donne le module d'origine.
- **VM Windows** : elle tombe si VT-x n'est pas actif ; vérifier
  `grep -c vmx /proc/cpuinfo` sur le nœud avant de conclure à une panne réseau.

---

## 16. Par où commencer, concrètement

1. `git log --oneline -5` et `git status` sur la VM : l'arbre doit être propre.
2. `python -m pytest -q tests/web` (8 s) : 42 verts, dont la parité.
3. Ouvrir `HOST-PARITY.md` → « Real work left » : quatorze lignes, chacune avec
   son plan. Les prendre dans l'ordre, une par une, avec la double preuve.
4. Après chaque lot : `scripts.dev_check` (~17 min), régénérer
   `HOST-PARITY.md`, mettre à jour ce document.
5. Ne pousser sur `main` que sur demande explicite de l'utilisateur.
