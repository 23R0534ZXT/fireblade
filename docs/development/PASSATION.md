# Passation — Fireblade, 17 novembre 2026 (nuit)

Document de reprise. Il dit où en est le dépôt, ce qui a été publié, ce qui a été fait
après la publication, ce qui reste ouvert, et comment vérifier. Le détail des procédures
vit dans le skill `fireblade-verification`.

## 1. État à l'instant

| Élément | État |
|---|---|
| Dépôt | `C:\Users\23R\dev\fireblade` sur la tour (192.168.1.167), branche `main` |
| Version | **0.4.2 publiée** le 17/11 à 19:34 UTC, `v0.4.2`, `latest`, pas de pré-release |
| Exe publié | 281 250 614 octets, SHA-256 `c7c358f2f8d8…`, auteur `23R0534ZXT` |
| CI | run 44168792898 sur `main` : 8 jobs verts (ruff, chemins longs, tests 3.12, exe x64, matrice des lecteurs, qualification visuelle, 3 GiB, exe 320 analyses) |
| Porte locale | 1 482 passés, 28 ignorés, 493 s, ruff propre |
| Recette VM | passée en entier le 17/11 (s0→s8, toutes EXIT 0) sur l'arbre 0.4.2 |
| VM de recette | `fb@192.168.1.80` (VM 300, Proxmox), harnais `C:\fireblade-test\harness` |

Rien n'est en cours. L'arbre est propre et poussé.

## 2. Ce que contient la 0.4.2

- **Vitesse** : 9,74 Gio en 6 min 0 s au lieu de 50 min 49 s, mêmes 246 analyses. Chaque
  fichier est lu dans son propre processus, un très gros fichier est découpé en tranches
  alignées sur les lignes, la provenance est écrite par l'import.
- **Huit corrections issues de la recette 0.4.1** : audit de couverture muet après une
  chasse, colonne Motif vide, export d'annotations à en-tête seul, libellés français,
  champs de filtre homonymes, colonne Read type (Structured/Raw), refus DTD sans contexte,
  en-têtes Zeek comptés comme lignes brutes.
- Notes complètes : `docs/development/RELEASE-NOTES.md`.

## 3. La passe de présentation du dépôt (17 novembre, après la publication)

Objectif dit par le mainteneur : « le repo doit être professionnel, on le fait tester à
des gens » — README, captures, tri des dossiers.

**README** — réécrit en page produit anglaise : une phrase de définition, bouton de
téléchargement, six capacités avec une capture chacune (espace de travail, filtres de
colonne, chronologie, chasse IOC, rapport d'imports), tableau du benchmark contre Timeline
Explorer avec les chiffres mesurés (56,6 s contre 108,3 s à l'ouverture sur 3,65 Go ;
1,1 Go contre 15,3 Go en mémoire), installation, cinq premières minutes, limites
assumées, nouveautés 0.4.2, liens vers la documentation.

**Captures** — reprises sur la VM de recette à 1280×800, en anglais, thème clair unique.
Les anciennes montraient la 0.2.2 en français avec les chemins du mainteneur. Scripts de
capture dans `/root/work/` : `shoot_readme.py`, `shoot_timeline.py`, `shoot_ioc.py`,
`shoot_detection.py` (à copier sur la VM dans `C:\fireblade-test\`).

**Documentation** — `docs/README.md` devient un index anglais qui ne pointe plus que vers
les guides, l'architecture, le benchmark et les validations. Sortis du dépôt :
`PUBLICATION.md`, `PRESENTATION-GITHUB.md`, `GITHUB-ABOUT.txt`, `artifacts-hermes.xml`,
`Fireblade (test local).cmd`. Copie dans `/root/work/fireblade-internal/`.

**GitHub** — description, topics (`dfir`, `digital-forensics`, `incident-response`,
`windows`, `timeline-analysis`, `ioc-hunting`, `forensic-tools`, `duckdb`), lien website
sur `/releases/latest`, formulaires d'issue traduits en anglais (le lien de contact
pointait vers un fil de test interne).

**Deux correctifs trouvés au passage** : le filtre de gravité Hayabusa proposait encore
`Faible / Moyenne / Élevée / Critique` en interface anglaise ; la bannière d'alerte
insérait le niveau brut dans une phrase traduite.

**Défaut de publication corrigé** : toutes les releases depuis 0.3.0 étaient marquées
pré-release, donc « Latest » sur GitHub pointait sur la 0.3.1. `v0.4.2` est repassée en
release normale et en `latest`.

Commits de cette passe : `b8bf6ef` (interface), `8db4721` (présentation), `54a51e2`
(formulaires d'issue), plus le présent document.

## 4. Ce qui reste ouvert

1. **Guides utilisateur en français.** `docs/guides/` est encore français alors que le
   README, les notes et l'interface sont anglais. C'est le plus gros écart de cohérence
   qui reste sur la surface publique. Traduction à mener guide par guide, en commençant
   par `FONCTIONNALITES.md` et `UTILISATION.md`.
2. **`docs/validation/` (143 rapports) est embarqué dans le `.exe`** :
   `scripts/windows/build.py` copie le dossier dans les ressources. On ne peut donc pas
   le retirer sans toucher au build, et le build local est impossible sur la tour (pas de
   SDK .NET). À faire avec une CI à disposition, pas à la légère.
3. **Résidu de traduction de la famille « exports »** — 234 entrées préparées, reportées
   à la 0.5.0.
4. **Chemins > 260 caractères** : limite assumée, exige `LongPathsEnabled=1`. Documentée
   dans les notes de version ; ne pas la mélanger à une passe de correction.
5. **0.5.0** : le mainteneur a annoncé un lot à venir, non décrit à ce jour.

## 5. Vérifier

- **La porte décide seule** : `set QT_QPA_PLATFORM=windows` puis
  `.venv\Scripts\python.exe -m scripts.dev_check` → `TOUT EST VERT`, ~8 minutes.
- **Jamais deux suites en même temps** : DuckDB prend un verrou, la seconde se fige sans
  message. C'est arrivé cette nuit et a coûté huit minutes.
- Un test lancé à la main sans `PYTHONUTF8=1` ment sur les noms accentués.
- La recette est le test final, en entier, sur un arbre dont la porte est verte.
- Tout correctif se ferme par : le correctif, un test de la voie de refus quand il y en a
  une, la porte verte, le rejeu des sections atteintes.
- Rien ne se pousse sur `main` sans accord explicite du mainteneur dans la session.

## 6. Pièges qui ont coûté du temps cette nuit

- **`git status` tronqué** par `| more` ou `| tail -N` : un fichier modifié peut
  disparaître de l'affichage et laisser croire que rien n'a changé. Vérifier avec
  `git diff --stat HEAD -- <fichier>` ou sans pagination.
- **La tour n'a ni `head`, ni `tail`, ni `findstr`** utilisables dans le shell de `ssh` :
  passer par des one-liners Python (`Path(...).read_text()`, `subprocess`).
- **Captures d'écran** : dans la fenêtre, la chronologie s'ouvre par
  `workbench.setCurrentIndex(window.timeline_tab_index)` ; `setCurrentWidget(panel)` ne
  suffit pas. Un thème unique se force par `apply_theme(app, 'light')` et
  `window.preferences.theme = 'light'`, sinon la capture hérite du mode sombre de la VM.
- **Le panneau de détail de la chronologie affiche des noms de colonnes bruts**
  (« Horodatage UTC ») : c'est de la donnée d'analyse, pas un libellé d'interface — ne pas
  le traiter comme un défaut.
- `translate(gabarit).format(valeur)` traduit le cadre et insère la valeur brute : c'est
  la cause la plus fréquente du français restant.
- Les releases du workflow sortent en **pré-release** : après chaque publication,
  vérifier `gh release list --json tagName,isPrerelease,isLatest` et repasser en `latest`.

## 7. Décisions à ne pas rouvrir

- Interface en anglais seul depuis la 0.3.2 ; les nouveaux libellés s'écrivent
  directement en anglais.
- Cette passation reste en français et vit dans le dépôt : c'est le document de travail du
  mainteneur, qui le lit par le lien brut GitHub.
- Releases publiées sous le compte `23R0534ZXT`, jamais par `github-actions[bot]`.
- Aucun push sur `main` sans accord explicite dans la session en cours.
- Une collecte publie ses analyses par famille ; les analyses par fichier restent sur
  disque, ce n'est pas une perte.
- Numéros : 0.x.0 pour un lot accumulé, 0.0.x pour un correctif.

## 8. Premier message de la prochaine session

Rien n'est en cours. La 0.4.2 est publiée et le dépôt a été remis au propre pour des
testeurs. Lis ce document, puis le skill `fireblade-verification`. Avant de toucher au
code : `git status` propre, porte verte. Le prochain chantier naturel est la traduction
des guides utilisateur (§4.1) ; le mainteneur doit présenter le lot 0.5.0 avant de
démarrer quoi que ce soit dessus.
