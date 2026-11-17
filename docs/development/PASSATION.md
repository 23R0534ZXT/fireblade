# Passation — Fireblade, 17 novembre 2026 (soir)

Document de reprise complet. Il dit où en est le code, ce que la recette de la 0.4.1 a
mesuré, ce qui a été corrigé et vérifié, ce qui reste à corriger, comment le vérifier, et
la séquence exacte de publication. Le détail des procédures vit dans le skill
`fireblade-verification` ; ce fichier est la vue d'ensemble, écrite pour être lue d'un bout
à l'autre avant de toucher au code.

**Objectif de la prochaine session, dit par le mainteneur : tout corriger, tout rendre
parfait, refaire une recette complète, puis publier.**

---

## 1. État exact, à l'instant de cette passation

| Élément | État |
|---|---|
| Dépôt | `C:\Users\23R\dev\fireblade` sur la tour, utilisateur `23R`, branche **`hermes/0.4.2`** |
| `main` | `32c84e3` — la 0.4.1 est publiée, `origin/main` au même commit |
| `hermes/0.4.2` | **10 commits devant `main`**, arbre propre, **rien n'est poussé** |
| Porte (dernier passage) | **1 459 passés, 28 ignorés**, ruff propre, fenêtre réelle — `TOUT EST VERT` |
| Release GitHub | `v0.4.1` seulement : exe 281 209 660 octets, SHA-256 `14ae688b…`, auteur `23R0534ZXT` |
| Recette | 0.4.1 passée en entier sur VM ; sur l'arbre final, seules `s3` et `s4` ont été rejouées |
| VM de recette | `fb@192.168.1.80` (Proxmox, VM 300), Windows 11 26H2 `en-us`, SSH par `/root/.ssh/id_ed25519` |

Le harnais de recette vit sur la VM dans `C:\fireblade-test\harness\` (sections `s0`…`s8`,
`sweep2.py`, `fbcommon.py`, `run-section-vm.ps1`, et `run-all-sections.ps1` pour enchaîner).
Les captures sont dans `C:\fireblade-test\shots\`, les journaux `*.log` et `journal.json`
dans le même dossier `harness`. Une copie des 145 captures et des constats est sur la
machine de contrôle dans `/root/work/vm-shots/` et `/root/work/recette/constats.md`.

---

## 2. Ce que contient la 0.4.2

### La vitesse (travail antérieur, commits `0e55c86`, `30a35a2`)

La même collecte de 9,74 Gio passe de **50 min 49 s à 6 min 0 s**, mêmes 246 analyses :
chaque fichier est lu dans son propre processus, un très gros fichier est découpé en
tranches alignées sur les lignes (CSV recollés à l'identique), et la provenance est écrite
par l'import au lieu d'être recopiée ligne à ligne. Mesures : quatre fichiers de 250 Mo
passent de 11,7 à 34,7 Mo/s ; un seul fichier de 250 Mo lu en huit tranches, de 22,8 s à
3,4 s.

### Les corrections issues de la recette (huit commits, chacun avec la porte verte)

1. **`7d32049` — l'audit de couverture ne retournait plus en silence.** Après une chasse
   IOC, `can_open_file()` restait faux et `launch()` faisait `return` sans un mot : le clic
   ne faisait rien. Il annonce l'attente, sonde toutes les 500 ms pendant 60 s, démarre seul
   dès que la requête libère la fenêtre, et explique quoi faire sinon.
2. **`7d32049` — la colonne Motif du bilan n'est plus vide.** Le motif vivait au niveau du
   run, du membre d'archive ou de l'avertissement, jamais au niveau du fichier :
   `entry_reason()` le remonte et le bilan l'affiche ; un fichier qu'aucun lecteur ne
   reconnaît dit `No reader recognised this file`.
3. **`7d32049` — l'export des annotations ne livre plus un fichier à en-tête seul.** Il
   recoupait les notes avec le filtre actif et écrivait un CSV vide sans le dire. Il refuse
   maintenant en donnant le compte détenu par l'analyse, et n'écrit rien.
4. **`5b8f914` — les libellés vus en français.** Neuf entrées ajoutées à la table, et
   surtout : les compteurs traduisaient **le gabarit avant d'y insérer le statut**
   (`translate('Import : {} …').format('Terminé')`), ce qui laissait le statut en français.
   Le statut est désormais traduit là où il est inséré. « erreur de lecteur » était traduit
   en « drive error » alors qu'il s'agit du lecteur de journal — corrigé en
   « reader error ».
5. **`bc31a71` — les champs de filtre de colonne.** Tous portaient le même texte d'aide
   français, et leur nom d'accessibilité annonçait « Filtrer la colonne 3 » (un numéro) au
   lieu de la colonne : ce qu'un lecteur d'écran débite. Le nom porte l'en-tête réel.
6. **`4c7ba92` — la colonne Read type écrit `Structured` / `Raw`.** `Structurée` et `Brute`
   étaient écrites comme des **données** par les parseurs, donc hors de portée de la table.
   Les compteurs acceptent encore les anciens mots français : une analyse de 0.4.1 continue
   de compter ses lignes brutes.
7. **`5854457` — le refus DTD dit quel fichier et quoi faire.** Un plan ou des préférences
   Timeline Explorer portant une DTD étaient refusés par la phrase brute du parseur, en
   français, sans nom de fichier ni remède.
8. **`cd097ee` — une déclaration Zeek n'est plus une ligne brute.** `#separator`, `#fields`,
   `#close`, `#Software` gardent leur ligne, leur offset et leur texte (la preuve est
   intacte) mais portent leur propre état, compté à part.
9. **`1308dd6` — les derniers français visibles.** La liste des filtres actifs affichait
   `Statut  Égal à (exact)  404` (en-tête et opérateur lus bruts) ; l'aide du bilan n'était
   pas traduite.

---

## 3. La recette de la 0.4.1 : ce qu'elle a mesuré

Passée sur une **VM Windows 11 neuve**, parce que la tour ne peut pas exécuter les outils
.NET : Smart App Control (Device Guard) refuse `EvtxECmd.dll` et RECmd ne revient jamais.
Sur la VM, EVTX, Hayabusa, Shellbags, WebCache, MFT, Prefetch et ruche fonctionnent.

- **8 sections + balayage, 286 étapes : 274 OK, 1 à revoir, 7 échecs.**
- **145 captures**, toutes relues (et c'est ainsi qu'on a trouvé la moitié des défauts).
- Import de référence : 227 fichiers, 199 complets, 23 à vérifier, 1 erreur, 4 non reconnus,
  1 007 s ; sur la tour, 259 fichiers / 13,92 Gio en 651 s.
- Chasse IOC : 177 778 correspondances sur 36 artefacts, 11 min 30 s sur la VM.

**Deux constats étaient faux, et c'est important pour la suite :** « la barre d'état affiche
Prêt en anglais » (les captures anglaises disent `Ready` ; j'avais lu la capture en mode
français) et « le résumé et le tableau ne comptent pas pareil » (199 + 23 + 1 + 4 = 227, tout
concorde ; j'avais lu un tableau filtré). Les deux sont rectifiés dans les constats.

**Un échec n'était pas un défaut produit :** les trois analyses Windows « non ouvertes »
(DEF-16) existent et sont publiées — mais la collecte publie ses analyses **fusionnées par
famille** (`Prefetch.csv`, `MFT et USN.csv`, `AppCompatCache.csv`, `EVTX.csv`), et les 23
analyses par fichier restent sur disque dans `Collectes/<horodatage>/analyses/`. Le harnais
cherchait des noms de **sources** (`kape.pf`, `$mft`, `system`). Corrigé en cherchant les
familles : rejeu vert.

---

## 4. Les vingt constats, un par un

| # | Constat | Verdict |
|---|---|---|
| 01 | Aide de l'onglet Imports en français | **À FAIRE** — ce sont des fichiers markdown affichés tels quels |
| 02 | Barre d'état « Prêt » en anglais | **FAUX** — les captures disent `Ready` |
| 03 | Tableau du bilan vide pendant l'import | **À FAIRE** — jamais corrigé, jamais re-vérifié |
| 04 | Colonne Motif vide | **CORRIGÉ** `7d32049` |
| 05 | Avertissements et motifs en français | **PARTIEL** — la table couvre 916 des 924 chaînes visibles |
| 06 | Compteurs et statut de collecte en français | **CORRIGÉ** `5b8f914` |
| 07 | Résumé et tableau ne comptent pas pareil | **FAUX** — 199+23+1+4 = 227 |
| 08 | Trois onglets d'analyse homonymes | **À FAIRE** — `analysis_label()` ne désambiguïse pas |
| 09 | En-têtes Zeek comptés comme lignes brutes | **CORRIGÉ** `cd097ee`, test dédié |
| 10 | Chemin d'analyse très long | **LIMITE ASSUMÉE** — exige `LongPathsEnabled=1` |
| 11 | Français dans la grille et les panneaux | **CORRIGÉ** en grande partie (`5b8f914`, `4c7ba92`, `1308dd6`) |
| 12 | Champs de filtre au même libellé | **CORRIGÉ** `bc31a71` |
| 13 | Panneau de chasse IOC à moitié français | **À RE-VÉRIFIER** — la table couvre les chaînes vues |
| 14 | Même libellé traduit ou non | **CORRIGÉ** par la traduction des valeurs insérées |
| 15 | Audit de couverture muet après une chasse | **CORRIGÉ** `7d32049`, rejoué en recette |
| 16 | Trois analyses Windows « non ouvertes » | **FAUX** — harnais corrigé, rejeu vert |
| 17 | Notes absentes des exports | **CORRIGÉ** `7d32049`, trois tests |
| 18 | Erreur DTD brute sans dire quoi | **CORRIGÉ** `5854457` |
| 19 | Préférences → Ressources illisibles | **PARTIEL** — libellés traduits, la valeur effective n'est toujours pas affichée |
| 20 | Balayage de traduction trop bavard | **CORRIGÉ** — 61 chaînes signalées → 9, dont 1 réelle |
| 21 | **Barre d'état surchargée** (nouveau) | **À FAIRE** — le libellé de source est comprimé à « 2 ité » |

---

## 5. Ce qui reste à corriger, dans l'ordre

### 5.1 La barre d'état est surchargée (DEF-21, cosmétique mais visible partout)

Sur toutes les captures, en bas à gauche, on lit `2 ité` puis `Fireblade 0.4.2` collés :
le `QLabel` de source (`self.source`, `setMaximumWidth(240)`, `ui/app.py:267`) est écrasé
par les widgets permanents voisins. Les permanents sont : `version_label`, `source`,
`rules_summary`, le badge de couverture, `last_case_save`, `disk_status` (masqué), plus la
barre de progression et le bouton d'arrêt pendant une collecte. À reprendre : réduire le
nombre de permanents, ou passer la source et le résumé en infobulle, et **vérifier par
capture** — c'est un jugement visuel, pas une assertion de test.

### 5.2 Le tableau du bilan pendant l'import (DEF-03)

Pendant une collecte, l'onglet Imports affiche son tableau vide alors que les compteurs
avancent. La collecte publie ses résultats au fil de l'eau (`Collection.ready` →
`publish_results`), mais l'onglet ne se rafraîchit qu'à la fin (`collection_finished`).
À brancher : un rafraîchissement périodique du modèle du bilan sur les documents publiés,
sans reconstruire la table à chaque fichier (le coût d'un tri complet sur 227 lignes est
négligeable, mais le faire 227 fois ne l'est pas).

### 5.3 L'aide de l'onglet Imports est en français (DEF-01)

Les guides sont des fichiers markdown affichés verbatim : ils demandent des jumeaux
`<NOM>-en.md` et un `guide_path()` qui tienne compte de la langue. Aucune entrée de table ne
peut les traduire.

### 5.4 Trois onglets d'analyse portent la même étiquette (DEF-08)

Quand plusieurs analyses d'une même famille sont ouvertes (par exemple trois `CarsDB.db`
produits par SQLECmd), leurs onglets sont identiques. `analysis_label()` doit
désambiguïser (suffixe par index ou par chemin court) — et la même règle sert au menu de
sélection.

### 5.5 Les préférences n'affichent pas la valeur effective (DEF-19)

`Memory per analysis`, `Threads · search and queries` et `Threads · import and parsing`
montrent « Current configuration » / « Automatic » au lieu d'une quantité. Le texte est
traduit depuis ce soir, mais l'utilisateur ne peut toujours pas lire **combien** de mémoire
et de threads sont réellement configurés. À régler en affichant la valeur calculée (la même
que celle de la barre d'effort) plutôt qu'un sentinelle.

### 5.6 Les messages du moteur restent en français (DEF-05)

`python -m scripts.i18n_inventory` dit : 924 chaînes françaises atteignent une interface,
916 traduites, 8 restantes (toutes des noms de fichiers de test). Le résidu réel n'est pas
dans cet inventaire : il est dans les messages d'erreur techniques profonds, affichés dans
les dialogues. À traiter par familles (collection, couverture, exports), en vérifiant que
`tests/test_translation_coverage.py` reste vert.

### 5.7 Les chemins longs (DEF-10)

Sans `LongPathsEnabled=1`, un chemin de plus de 260 caractères échoue sur un Windows 11
neuf : deux tests tombent (`test_windows_extended_long_unicode_paths` et le sélecteur
CatScale). C'est une **limite assumée** documentée dans les notes de version. Si le
mainteneur veut la lever, il faut préfixer les écritures `\\?\` dans les rédacteurs de
fichiers — un chantier à part, à ne pas mêler à une passe de correction.

---

## 6. La méthode de vérification (à ne pas contourner)

1. **La porte décide, seule** :
   `set QT_QPA_PLATFORM=windows` puis `.venv\Scripts\python.exe -m scripts.dev_check`
   → doit finir par `TOUT EST VERT`, 1 459 passés / 28 ignorés, ruff inclus. ~8 minutes.
   Ne jamais lancer deux suites en même temps : DuckDB prend un verrou et la seconde se
   fige sans message.
2. **Un test lancé à la main sans `PYTHONUTF8=1` ment** : un nom de fichier accentué le fait
   échouer sur un arbre que la porte appelle vert. Vérifier avec la porte, ou exporter la
   variable.
3. **Stash pour prouver qu'un échec précède ta modification** (`git stash push -- <fichier>`,
   relancer le test, `git stash pop`).
4. **La recette est le test final**, en entier, depuis `s0`, sur un arbre dont la porte est
   verte. Sections **une par une** (`run-section-vm.ps1`), ou enchaînées avec
   `run-all-sections.ps1 -list s0_smoke.py:f0,s1_import.py:f1,…`. Chaque étape laisse une
   capture, chaque capture est lue — et zoomée avant d'en tirer un défaut.
5. **Un FAIL est une hypothèse** tant que les données sur disque ne l'ont pas confirmé :
   lire `collection.json` (`documents`, `files`, `runs`), les `.timeline` et les `bookmarks`
   en `read_only` avant de toucher au code produit.
6. Tout correctif se ferme par : le correctif, un test de la **voie de refus** quand il y en
   a une, la porte verte, et le rejeu des sections qu'il peut atteindre.

---

## 7. Pièges qui ont coûté du temps cette fois

- **`findstr` ne trouve pas un texte accentué** (page de code de la console) : chercher avec
  un script Python qui lit les octets en UTF-8.
- **Une capture se lit au zoom.** Une vignette m'a fait enregistrer « six boutons » qui
  étaient les champs de filtre d'une ligne par colonne, et un `Contient…` qui était un
  `Content…`.
- **`translate(gabarit).format(valeur)` traduit le cadre et insère la valeur brute.** C'est
  la cause de la majorité du français restant — quatre sites corrigés, d'autres peut-être.
- **`setSpecialValueText` échappe au mécanisme de langue** : un texte de valeur spéciale
  doit être enveloppé à la main.
- **`from fireblade.core.i18n import translate` manque parfois** dans un module : l'ajouter
  après le dernier import (position calculée par `ast`, jamais « après la ligne 3 » : un
  import multi-lignes casse).
- **Les fichiers du dépôt sont en CRLF**, certains documents en LF : convertir une seule
  fois, sinon `\r\r\n` et l'ancre ne correspond plus (`expected 1 match, found 0`).
- **Sur la VM, l'index de chronologie est lent** (I/O) : 20 minutes sur 38 analyses là où la
  tour met des secondes. Ce n'est pas un blocage — `py-spy dump` montre le thread de
  construction actif dans `csv_chunks`.
- **Les anciennes tâches planifiées `FB*` se déclenchent au réveil** de la tour et lancent
  plusieurs sections à la fois. Les supprimer avant toute passe
  (`schtasks /delete /tn FB<tag> /f`).

---

## 8. Décisions à ne pas rouvrir

- L'interface est en **anglais seul** depuis la 0.3.2 ; les nouveaux libellés s'écrivent
  directement en anglais.
- **`PASSATION.md` et les constats de recette restent en français** ; le reste de la surface
  publiée est en anglais, titres de releases et packs auxiliaires compris.
- **Aucun push sur `main` sans accord explicite du mainteneur dans la session en cours.** Une
  passation qui liste les étapes de publication n'est pas une autorisation.
- Les releases sont publiées **sous le compte `23R0534ZXT`**, jamais par
  `github-actions[bot]` ; si le bot l'a publiée, la recréer à l'identique (même exe, même
  SHA-256).
- Une collecte publie ses analyses **par famille** ; les analyses par fichier restent sur
  disque, ce n'est pas une perte.
- Numéros : `0.x.0` pour un lot accumulé, `0.0.x` pour un correctif.

---

## 9. La publication, pas à pas (après la recette complète et verte)

```bat
set GIT=C:\Users\23R\AppData\Local\hermes\tools\git-2.56.1+1-win32-x64\cmd\git.exe
cd /d C:\Users\23R\dev\fireblade
%GIT% branch --show-current          rem doit dire hermes/0.4.2
%GIT% status --short                 rem doit être vide
.venv\Scripts\python.exe -m scripts.dev_check   rem TOUT EST VERT
%GIT% checkout main
%GIT% merge --ff-only hermes/0.4.2
%GIT% push origin main
%GIT% tag -a v0.4.2 -m "0.4.2: the same collection in six minutes, and what the acceptance run found"
%GIT% push origin v0.4.2
gh run watch                       rem la CI construit, vérifie et publie
```

Puis vérifier la release :

```bat
gh release view v0.4.2 --repo 23R0534ZXT/fireblade --json author,assets,isPrerelease
```

Si `author.login` vaut `github-actions[bot]`, recréer la release sous le mainteneur en
réutilisant l'exe déjà vérifié (même SHA-256) — procédure dans le skill, section
« Releasing a version ». Ne jamais reconstruire pour ce motif.

Avant de taguer : la version doit être `0.4.2` dans `pyproject.toml` **et**
`src/fireblade/__init__.py` (la porte compare les deux), la section 0.4.2 est en tête de
`docs/development/RELEASE-NOTES.md`, et ce fichier-ci est à jour.

---

## 10. Premier message de la prochaine session

> Reprise de la 0.4.2. Lis ce fichier en entier, puis le skill `fireblade-verification`.
> La branche `hermes/0.4.2` porte 10 commits, arbre propre, porte verte, rien de poussé.
> Objectif : corriger les points 5.1 à 5.7 (§5) un par un, chacun avec la porte verte, puis
> refaire la recette complète sur la VM (`run-all-sections.ps1`) et publier selon §9.
> Commence par relire les constats dans `/root/work/recette/constats.md` et par vérifier que
> `git status` est propre et que la porte passe, avant de toucher à quoi que ce soit.

---

*Fin de la passation. 10 commits, 8 corrections vérifiées, 2 constats rectifiés, 1 faux
échec expliqué, 6 points ouverts décrits ci-dessus.*
