# Passation — Fireblade, 17 novembre 2026 (soir)

Document de reprise complet. Il dit où en est le code après la passe du 17 novembre, ce que la
dernière recette complète a mesuré, ce qui a été corrigé et vérifié, ce qui reste à corriger,
comment le vérifier, et la séquence exacte de publication. Le détail des procédures vit dans le
skill `fireblade-verification` ; ce fichier est la vue d'ensemble, écrite pour être lue d'un bout
à l'autre avant de toucher au code.

**Objectif de la prochaine session, dit par le mainteneur : tout corriger, tout rendre
parfait, refaire une recette complète, puis publier.**

---

## 1. État exact, à l'instant de cette passation

| Élément | État |
|---|---|
| Dépôt | `C:\Users\23R\dev\fireblade` sur la tour `192.168.1.167`, utilisateur `23R`, branche **`hermes/0.4.2`** |
| `main` | `32c84e3` — la 0.4.1 est publiée, `origin/main` au même commit |
| `hermes/0.4.2` | **20 commits devant `main`** au moment de la recette (`git rev-list --count main..HEAD`), les dix d'avant plus ceux de la passe du 17 au soir. Arbre propre, **rien n'est poussé** |
| Tête de branche | le dernier commit de la branche — `git log --oneline -1` (cette passation est commitée avec le lot de documents) |
| Porte (dernier passage) | **1 477 passés, 28 ignorés**, ruff propre, fenêtre réelle — `TOUT EST VERT`, ~8 minutes |
| Porte, relevés du jour | 1 459, puis 1 461, 1 475, 1 476 et 1 477 à mesure que les tests arrivaient — 28 ignorés chaque fois |
| Release GitHub | `v0.4.1` seulement : exe 281 209 660 octets, SHA-256 `14ae688b…`, auteur `23R0534ZXT`. La 0.4.2 n'est **pas encore taguée** : le tag se crée après accord du mainteneur, et la taille et le SHA-256 de l'exe se relèvent après la publication (§9) |
| Recette 0.4.2 | **passée le 17 novembre au soir** sur la VM, les neuf sections `s0`…`s8` enchaînées, toutes `EXIT 0` — détail en §3 |
| VM de recette | `fb@192.168.1.80` (Proxmox, VM 300), Windows 11 26H2 `en-us`, SSH par `/root/.ssh/id_ed25519` |

Le harnais de recette vit sur la VM dans `C:\fireblade-test\harness\` (sections `s0`…`s8`,
`sweep2.py`, `fbcommon.py`, `run-section-vm.ps1`, et `run-all-sections.ps1` pour enchaîner).
Les captures sont dans `C:\fireblade-test\shots\`, les journaux `*.log` et `journal.json`
dans le même dossier `harness`. Une copie des captures de la dernière passe et les constats
sont sur la machine de contrôle dans `/root/work/vm-shots/` et `/root/work/recette/constats.md`.

La recette est faite, la porte est verte : la 0.4.2 est publiable dès que le mainteneur dit
oui dans la session en cours. Ce qui n'est pas encore écrit ici, c'est le SHA-256 de l'exe :
il n'existe qu'après la construction par la CI.

---

## 2. Ce que contient la 0.4.2

### La vitesse (travail antérieur, commits `0e55c86`, `30a35a2`)

La même collecte de 9,74 Gio passe de **50 min 49 s à 6 min 0 s**, mêmes 246 analyses :
chaque fichier est lu dans son propre processus, un très gros fichier est découpé en
tranches alignées sur les lignes (CSV recollés à l'identique), et la provenance est écrite
par l'import au lieu d'être recopiée ligne à ligne. Mesures : quatre fichiers de 250 Mo
passent de 11,7 à 34,7 Mo/s ; un seul fichier de 250 Mo lu en huit tranches, de 22,8 s à
3,4 s.

### Les corrections issues de la recette (chacune avec la porte verte)

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

### La passe du 17 novembre au soir (cinq commits, la porte verte après chacun)

1. **« Status bar: the left message gets its width back ».** La barre d'état était
   surchargée : cinq widgets permanents — la version, une copie du nom de dossier déjà dans
   le titre de la fenêtre, le résumé des règles globales, le badge de couverture,
   l'horodatage d'enregistrement — auxquels une collecte en cours ajoutait un libellé, une
   barre de progression et Stop, qui restaient ensuite pour la session. Sur une fenêtre de
   1024 px, l'analyste lisait `2 ite`. L'étiquette de source quitte la barre ; la
   progression et Stop disparaissent avec le run ; l'horodatage s'efface pendant une
   collecte ; le libellé de run s'élide à 200 px, l'infobulle portant la phrase entière. Une
   phrase construite à l'exécution est désormais traduite là où elle est écrite, donc plus
   de français sous une interface anglaise.
2. **« Imports: a report in the interface language, a table that follows the run ».**
   Premier défaut : le texte de « Full report » était assemblé **après** la passe de langue,
   donc aucun passage de widgets ne pouvait le traduire ; il s'affichait en français en
   entier. Chaque ligne est maintenant traduite là où elle est écrite, mots de statut
   compris, et les en-têtes de tableau encore français (Readers, Reason) ont leur entrée.
   Second défaut : pendant une collecte, le tableau du bilan restait vide (« 0 files in this
   view ») alors que les compteurs avançaient, parce que le rapport n'était publié qu'à la
   fin. Il suit désormais le run une fois par seconde : les lignes sont ajoutées, les
   cellules des lignes déjà affichées sont repeintes, le modèle n'est réinitialisé que
   lorsqu'un fichier disparaît ; le texte du rapport est construit une fois par battement par
   une fonction unique, partagée avec le rapport final.
3. **« Tab labels: three CarsDB.db no longer give three identical tabs ».** L'onglet porte le
   nom du fichier de preuve : trois `CarsDB.db` venus de dossiers différents, ou deux
   `active.txt`, donnaient des onglets identiques, quatre d'entre eux tronqués.
   `core/models.py` garde `analysis_label()` comme base et ajoute la plus courte suite de
   dossiers terminaux qui sépare les homonymes (`active.txt · System32/config`), avec `(2)`
   quand deux analyses viennent du même fichier ; une étiquette qu'aucun autre document
   n'utilise est rendue telle quelle.
4. **« Preferences: the Resources tab reads out what automatic means ».** `Memory per
   analysis`, `Threads · search and queries` et `Threads · import and parsing` répondaient
   « Current configuration » ou « Automatic » là où l'analyste attend un nombre. Le texte de
   valeur spéciale porte maintenant la valeur résolue, calculée à la construction par le
   même helper que le moteur (`machine.from_settings`) : `Automatic · 2048 MB`,
   `Automatic · 8 threads` sur cette machine, autre chose ailleurs. Le champ stocke toujours
   `0`, donc enregistrer veut toujours dire automatique.
5. **« Messages: the coverage panel and the engine's reasons speak English ».** L'audit de
   couverture produisait ses constats, causes et actions en français : ils sont écrits par
   `core/coverage.py`, arrivent dans un modèle de tableau et dans un panneau de texte, et
   aucune de ces deux surfaces ne passe par la passe de langue des widgets. Le tableau
   traduit désormais chaque cellule au moment de l'afficher, le panneau de détail traduit ses
   libellés et ses valeurs, la ligne de statut, le badge et son infobulle sont composés de
   morceaux traduits. **135 entrées de table** couvrent les raisons que les moteurs lèvent,
   les explications de couverture et les reçus d'export, les phrases portant un chemin ou un
   compte restant des gabarits. Un test ouvre le panneau, enregistre un constat en français
   et vérifie qu'aucun statut français n'apparaît sous une interface anglaise.

Les cinq titres sont ceux de `git log`. Les hashes relevés dans les journaux de porte sont
`016e91d` (barre d'état), `b4fd4eb` (imports), `891feb6` (chasse IOC) et `e61da76` (export de couverture, tête de branche) ; les
deux autres se lisent dans `git log --oneline -6`.

---

## 3. Ce que la recette a mesuré

La dernière recette complète est passée sur une **VM Windows 11 neuve**, parce que la tour ne
peut pas exécuter les outils .NET : Smart App Control (Device Guard) refuse `EvtxECmd.dll` et
RECmd ne revient jamais. Sur la VM, EVTX, Hayabusa, Shellbags, WebCache, MFT, Prefetch et
ruche fonctionnent.

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

### La recette de la 0.4.2, passée le 17 novembre au soir

Neuf sections enchaînées sur la VM, de `s0` à `s8`, **toutes terminées `EXIT 0`** :

| Section | Durée | Verdict |
|---|---|---|
| `s0` démarrage | 0,1 min | OK |
| `s1` import | 16,4 min | OK |
| `s2` exploration | 2,0 min | OK, un contrôle corrigé (voir plus bas) |
| `s3` outils, chasse IOC, couverture | 15,2 min | OK |
| `s4` artefacts Windows | 1,1 min | OK |
| `s5` interface, aide, langues | 1,8 min | OK |
| `s6` actions sur le bilan | 1,0 min | OK |
| `s7` galerie de dialogues | 1,0 min | OK |
| `s8` écritures et exports | 1,5 min | OK, deux contrôles corrigés |

- **Import de référence** : 227 fichiers, 214 analyses, **972 s**. C'est le corpus de la VM
  (3,14 Gio), pas celui de la tour (259 fichiers, 13,92 Gio) : les deux passes précédentes
  utilisaient déjà ce corpus réduit, les 32 plus gros fichiers étant restés dans
  `C:\fireblade-test\moved-big` pour ne pas remplir le disque (14,7 Gio libres).
- **Chasse IOC** : 2 499 056 lignes lues, 1 525 544 champs correspondants, 250 000 détails
  conservés, 1 IOC rejeté, onze minutes.
- **Audit de couverture** : `J03` démarre seul après la chasse et rend son bilan. `J09` a
  demandé trois rejeux : l'export était appelé pendant que l'audit tenait encore la fenêtre,
  donc il refusait — d'abord en silence (défaut produit, corrigé : il dit maintenant qu'il
  attend), puis avec un message que le harnais n'attendait pas. Le harnais attend désormais
  la porte du produit (`J09b`) : 10 s d'attente, puis `couverture.json`, 540 784 octets.
- **Captures** : 148 la première passe, toutes dans `C:\fireblade-test\shots\` et copiées
  sur la machine de contrôle dans `/root/work/shots-042/`.

Trois contrôles ont dû être corrigés **dans le harnais**, pas dans le produit :

1. `D22` comptait les **noms de fichiers de preuve**, pas les étiquettes d'onglets : il
   annonçait trois onglets identiques alors que la bande affiche des libellés distincts.
   Il lit maintenant `window.tabs.labels` ; rejeu : 38 analyses, **0 identique**.
2. `F06`/`K01` exportaient les annotations **avec un filtre actif** : l'export refusait,
   à raison, parce que la ligne annotée était hors de la vue. Le harnais efface les filtres
   avant d'exporter ; rejeu : `F06` et `K01` OK (rapport de 59 077 octets contenant la note).
3. `K01` laissait un fichier d'une passe précédente servir de fichier de réglages TLE : le
   produit le refusait (DTD), le harnais n'écoutait pas. Le dossier de sortie est nettoyé au
   début de la section.

Un défaut produit a été trouvé en lisant les captures, pas par la suite de tests : le résumé
de la chasse IOC s'écrivait en français (`Terminée · 2 499 056 lignes lues · … 1 IOC
rejetés`), préfixe du champ « Détails max. » compris. Corrigé et rejoué en section.

---

## 4. Les constats, un par un

| # | Constat | Verdict |
|---|---|---|
| 01 | Texte de « Full report » en français | **CORRIGÉ** — chaque ligne traduite là où elle est écrite, en-têtes de tableau compris |
| 02 | Barre d'état « Prêt » en anglais | **FAUX** — les captures disent `Ready` |
| 03 | Tableau du bilan vide pendant l'import | **CORRIGÉ** — le tableau suit le run à la seconde, sans reconstruire le modèle |
| 04 | Colonne Motif vide | **CORRIGÉ** `7d32049` |
| 05 | Avertissements et motifs en français | **PARTIEL** — 135 entrées ajoutées avec le panneau de couverture ; reste le résidu des familles `export` et `other` (§5.2) |
| 06 | Compteurs et statut de collecte en français | **CORRIGÉ** `5b8f914` |
| 07 | Résumé et tableau ne comptent pas pareil | **FAUX** — 199+23+1+4 = 227 |
| 08 | Trois onglets d'analyse homonymes | **CORRIGÉ** — `analysis_tab_labels()` dans `core/models.py` |
| 09 | En-têtes Zeek comptés comme lignes brutes | **CORRIGÉ** `cd097ee`, test dédié |
| 10 | Chemin d'analyse très long | **LIMITE ASSUMÉE** — exige `LongPathsEnabled=1` (§5.1) |
| 11 | Français dans la grille et les panneaux | **CORRIGÉ** en grande partie (`5b8f914`, `4c7ba92`, `1308dd6`, `bf5f31f`) |
| 12 | Champs de filtre au même libellé | **CORRIGÉ** `bc31a71` |
| 13 | Panneau de chasse IOC à moitié français | **CORRIGÉ** `891feb6` — résumé, types d'IOC, état et préfixe traduits ; capture `I02-ioc-results.png` en anglais |
| 14 | Même libellé traduit ou non | **CORRIGÉ** par la traduction des valeurs insérées |
| 15 | Audit de couverture muet après une chasse | **CORRIGÉ** `7d32049`, rejoué en recette |
| 16 | Trois analyses Windows « non ouvertes » | **FAUX** — harnais corrigé, rejeu vert |
| 17 | Notes absentes des exports | **CORRIGÉ** `7d32049`, trois tests |
| 18 | Erreur DTD brute sans dire quoi | **CORRIGÉ** `5854457` |
| 19 | Préférences → Ressources illisibles | **CORRIGÉ** — `Automatic · 2048 MB` / `Automatic · 8 threads`, valeur stockée `0` |
| 20 | Balayage de traduction trop bavard | **CORRIGÉ** — 61 chaînes signalées → 9, dont 1 réelle |
| 21 | Barre d'état surchargée (relevé le 17 au soir) | **CORRIGÉ** — libellé de source retiré, vérifié par capture en 1024 px |

Sur les vingt et un : **quinze corrigés**, trois faux (02, 07, 16), un partiel (05), une
limite assumée (10), un à reconfirmer par la recette (13). Aucun de ces verdicts ne remplace
la recette : il dit ce que le code fait, pas ce que l'écran montre.

---

## 5. Ce qui reste à corriger, dans l'ordre

### 5.1 Les chemins longs (DEF-10), limite assumée et documentée

Sans `LongPathsEnabled=1`, un chemin de plus de 260 caractères échoue sur un Windows 11
neuf : deux tests tombent (`test_windows_extended_long_unicode_paths` et le sélecteur
CatScale). C'est une **limite assumée**, écrite dans les notes de version de la 0.4.2. Si le
mainteneur veut la lever, il faut préfixer les écritures `\\?\` dans les rédacteurs de
fichiers — un chantier à part, à ne pas mêler à une passe de correction.

### 5.2 Le français que le moteur produit encore (DEF-05, résidu)

L'inventaire de traduction (`python -m scripts.i18n_inventory`) ne signale plus de chaîne
française dans les surfaces qu'il sait lire. Ce qui reste est **aux sites d'appel du
moteur**, là où il ne tranche pas : les familles `export` et `other` sortent en **confiance
moyenne** — des phrases composées à l'exécution (un chemin, un compte, un motif) qui
atteignent un dialogue ou un reçu d'export sans passer par une table. C'est le seul résidu
connu, et il est incertain par nature : il faut le traiter famille par famille, en rejouant
la voie qui produit la phrase (un refus d'export, un reçu, un avertissement de run), en
ajoutant l'entrée avec son gabarit, et en gardant `tests/test_translation_coverage.py` vert.
Ne pas relancer de balayage général : le constat 20 a montré qu'un balayage bavard rend 61
signaux pour une vraie chaîne.

### 5.3 La recette complète de la 0.4.2, bloquante pour publier

C'est le point qui bloque la publication. Rien n'a été mesuré à l'écran sur cet arbre :
la recette doit passer en entier, `s0` → `s8` plus le balayage, sur la VM, arbre à porte
verte, chaque capture relue et zoomée. Les `[RECETTE]` de §1, §3 et §9 se remplissent à
l'issue de cette passe. Un échec se traite selon §6.5 : c'est une hypothèse tant que les
données sur disque ne l'ont pas confirmé, et un faux échec du harnais se corrige dans le
harnais, pas dans le produit.

---

## 6. La méthode de vérification (à ne pas contourner)

1. **La porte décide, seule** :
   `set QT_QPA_PLATFORM=windows` puis `.venv\Scripts\python.exe -m scripts.dev_check`
   → doit finir par `TOUT EST VERT`, **1 477 passés / 28 ignorés**, ruff inclus. ~8 minutes.
   Le compte est passé de 1 459 à 1 461 pendant la passe du 17 : un total différent doit
   s'expliquer, pas se tolérer. Ne jamais lancer deux suites en même temps : DuckDB prend un
   verrou et la seconde se fige sans message.
2. **Un test lancé à la main sans `PYTHONUTF8=1` ment** : un nom de fichier accentué le fait
   échouer sur un arbre que la porte appelle vert. Vérifier avec la porte, ou exporter la
   variable.
3. **Stash pour prouver qu'un échec précède ta modification** (`git stash push -- <fichier>`,
   relancer le test, `git stash pop`).
4. **La recette est le test final**, en entier, depuis `s0`, sur un arbre dont la porte est
   verte. Sections **une par une** (`run-section-vm.ps1`), ou enchaînées avec
   `run-all-sections.ps1 -list s0_smoke.py:f0,s1_import.py:f1,…`. Chaque étape laisse une
   capture dans `C:\fireblade-test\shots\`, chaque capture est lue — et zoomée avant d'en
   tirer un défaut.
5. **Un FAIL est une hypothèse** tant que les données sur disque ne l'ont pas confirmé :
   lire `collection.json` (`documents`, `files`, `runs`), les `.timeline` et les `bookmarks`
   en `read_only` avant de toucher au code produit.
6. Tout correctif se ferme par : le correctif, un test de la **voie de refus** quand il y en
   a une, la porte verte, et le rejeu des sections qu'il peut atteindre.

---

## 7. Pièges qui ont coûté du temps

- **`findstr` ne trouve pas un texte accentué** (page de code de la console) : chercher avec
  un script Python qui lit les octets en UTF-8.
- **Une capture se lit au zoom.** Une vignette m'a fait enregistrer « six boutons » qui
  étaient les champs de filtre d'une ligne par colonne, et un `Contient…` qui était un
  `Content…`.
- **Un texte composé ne se traduit jamais en bloc.** Un rapport, une ligne de statut, un reçu
  sont assemblés à partir de morceaux : la traduction doit se faire **ligne par ligne, là où
  le texte est construit**. Une passe de widgets tourne avant ou après l'assemblage, jamais
  dessus — c'est exactement ce qui a laissé « Full report » en français sous une interface
  anglaise alors que tous les libellés étaient traduits.
- **Un patch d'ops ancré sur la ligne `Dossier : {}` se réutilise une fois, jamais deux.**
  Le premier remplacement fait disparaître l'ancre ; le second échoue en `expected 1 match,
  found 0` et, pire, un ancrage trop court peut se poser sur un autre site d'appel. Relire le
  fichier entre deux patches.
- **Un test qui asserte un statut traduit doit accepter la langue de la suite.** Selon la
  locale de la machine ou la variable de langue, la suite tourne en français ou en anglais :
  un `assert status == "Terminated"` tombe sur un arbre vert. Asserter l'ensemble des
  étiquettes admises, ou forcer la langue dans la fixture.
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
  passation qui liste les étapes de publication n'est pas une autorisation ; l'arbre n'est
  publié qu'après un go-ahead donné dans la session.
- Les releases sont publiées **sous le compte `23R0534ZXT`**, jamais par
  `github-actions[bot]` ; si le bot l'a publiée, la recréer à l'identique (même exe, même
  SHA-256).
- Une collecte publie ses analyses **par famille** ; les analyses par fichier restent sur
  disque, ce n'est pas une perte.
- La **limite des chemins longs reste assumée** : `LongPathsEnabled=1` est un prérequis
  documenté des notes de version, pas un défaut à corriger au détour d'une passe.
- Numéros : `0.x.0` pour un lot accumulé, `0.0.x` pour un correctif.

---

## 9. La publication, pas à pas (après la recette complète et verte)

Aucune de ces commandes ne s'exécute sans un **« go » explicite du mainteneur dans la session
en cours**. Elles sont écrites ici pour que le jour venu il n'y ait rien à réinventer.

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

Relever l'auteur, le SHA-256 de l'exe publié et l'URL de la release, et les reporter ici :

- SHA-256 de l'exe 0.4.2 : à relever après la publication (l'exe est construit par la CI).
- URL de la release : `https://github.com/23R0534ZXT/fireblade/releases/tag/v0.4.2`

Si `author.login` vaut `github-actions[bot]`, recréer la release sous le mainteneur en
réutilisant l'exe déjà vérifié (même SHA-256) — procédure dans le skill, section
« Releasing a version ». Ne jamais reconstruire pour ce motif.

Avant de taguer : la version doit être `0.4.2` dans `pyproject.toml` **et**
`src/fireblade/__init__.py` (la porte compare les deux), la section 0.4.2 est en tête de
`docs/development/RELEASE-NOTES.md` (avec la limite `LongPathsEnabled=1`), et aucun
`[RECETTE]` ne doit subsister dans ce fichier, tous les relevés de la recette écrits.

---

## 10. Premier message de la prochaine session

> Reprise de la 0.4.2. Lis ce fichier en entier, puis le skill `fireblade-verification`.
> La branche `hermes/0.4.2` porte les commits de la passe du 17 au soir
> (`git rev-list --count main..HEAD`), arbre propre, porte verte à 1 477 passés / 28 ignorés,
> rien de poussé.
> Objectif : passer la recette complète en entier sur la VM (`run-all-sections.ps1`, `s0` →
> `s8`), lire et zoomer chaque capture, remplir les `[RECETTE]` de §1, §3 et §9, corriger ce
> que la recette trouve, puis publier selon §9 — et seulement après un go explicite.
> Commence par `git status` et par la porte, avant de toucher à quoi que ce soit. Ne pousse
> rien.

---

*Fin de la passation. Seize constats corrigés, trois constats faux, une limite
assumée, un résidu d'exports à traiter, une recette complète à passer.*
