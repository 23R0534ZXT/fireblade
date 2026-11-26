# Passation — Fireblade, 18 novembre 2026 (soirée)

Document de reprise. Il dit où en est le dépôt, ce qui a été construit, ce qui est
mesuré, ce qui reste ouvert, et comment vérifier. Le détail des procédures vit dans le
skill `fireblade-verification`.

## 1. Où vit le travail

**Tout se fait depuis Proxmox, sur la VM Windows 11** `fb@192.168.1.80` (VM 300,
`win11-dfir`, 4 cœurs / 8 Go, `C:\Users\fb\dev\fireblade`). La tour n'est plus utilisée.
Git de la VM : `C:\Users\fb\tools\git\cmd\git.exe`. Interpréteur :
`C:\Users\fb\dev\fireblade\.venv\Scripts\python.exe` (3.12.10).

## 2. État à l'instant

| Élément | État |
|---|---|
| Branche | `hermes/0.6.0-assistant` (la 0.6.1 y est construite) ; `main` porte la 0.6.0 |
| Version | **0.6.1 en préparation** : `pyproject.toml` et `__init__.py` à 0.6.1 |
| 0.6.0 publiée | tag `v0.6.0`, `Fireblade-0.6.0-win64.zip` 282 888 804 o, SHA-256 `e2e79d6c…`, auteur `23R0534ZXT`, *prerelease* |
| 0.5.2 publiée | tag `v0.5.2`, archive sous 220 caractères au plus long chemin |
| Porte | verte : **1616 passés, 28 ignorés, 968 s** — sur l'arbre exact de la 0.6.1 |
| Recette | `s19_chat_061` : D00–D10 verts — cas piégé, analyse en français qui nomme `updsvc` et `C:\Temp\u.exe`, historique rouvert depuis le dossier, contenu du case inchangé après deux tours |

## 2 bis. Ce que contient la 0.6.1 — l'assistant analyste

- **L'historique appartient au dossier.** Chaque tour s'écrit dans
  `<case>/assistant/conversation-<date>.jsonl` au moment où il se produit (`fsync`), et le
  panneau relit ce dossier : liste des conversations, `New`, réouverture. Rien dans le
  profil de l'application, donc une conversation se rejoue sur une autre machine qui a le
  dossier. Une ligne tronquée coûte un tour, jamais le fil.
- **Une méthode écrite, pas une consigne.** `METHOD` dans `core/assistant_chat.py` :
  transformer la question en décision, séparer observation et inférence, ne jamais lire un
  horodatage seul, nommer l'explication bénigne qui colle aux mêmes lignes, dire ce qui
  manque et quelle preuve trancherait. La réponse commence par le verdict, puis les
  preuves, puis l'alternative non écartée, puis une vérification concrète.
- **Le premier passage n'est plus laissé au modèle** : aperçu, constats, fenêtre de cinq
  minutes autour du plus grave, puis la même fenêtre en ordre chronologique. Ensuite
  seulement, le modèle choisit jusqu'à deux lectures supplémentaires parmi `around`,
  `sequence`, `entity`, `rare`, `stats`, `timeline`. Une lecture vide arrête la fouille au
  lieu de rendre une page blanche.
- **Elle analyse, elle n'agit pas.** `select_only()` refuse tout ce qui n'est pas
  `SELECT`/`PRAGMA`/`DESCRIBE` avant d'atteindre DuckDB, et la méthode le dit dans le
  prompt. Mesuré en recette : l'empreinte SHA-256 du fichier d'analyse est identique avant
  et après un cycle question/réponse/seconde question.

## 3. Ce que contient la 0.5.1 — l'import

Le sujet de cette version : **aucun import ne doit échouer en silence**. Ce qui existe
maintenant, et qui a été mesuré par les tests et par la recette :

- **Une opération, plusieurs sources** : le sélecteur prend des fichiers **et** des
  dossiers dans une même liste (`SourcesDialog`), lus en une seule collecte — un rapport,
  un journal, un dossier de travail. Un dossier déjà contenu dans un autre n'est pas lu
  deux fois.
- **Reprise** : `resume()` relit seulement les lignes `pending`/`cancelled` et celles dont
  le fichier d'analyse a disparu ; ce qui est fait reste fait. Un rendu fusionné
  (`raw_documents`) est reconstruit depuis ses analyses au lieu d'être cru sur parole.
  Côté interface, `Resume an import…` propose la reprise quand il reste des fichiers.
- **Doublons** : détection sur le **SHA-256 de la preuve**, dans l'opération et entre les
  imports d'un même case via `Collectes/import-index.json`. La seconde copie est une ligne
  `Duplicate` dont le motif nomme la copie lue ; elle ne produit pas d'onglet.
  **Exception assumée** : une collecte disque (`deduplicate_content = False`) garde deux
  artefacts identiques trouvés à deux endroits — c'est la localisation qui fait la preuve.
- **Preuve après écriture** : chaque analyse est rouverte en lecture seule et comptée
  contre le nombre enregistré à l'import (`verify_analysis`), verdict par document et
  résumé `Vérification : N contrôlées · N en échec` ; un écart est une ligne du journal.
- **Journal** : `journal.jsonl` à côté de `collection.json`, une ligne JSON par événement
  (horodatage UTC, secondes depuis le début). Début/fin d'opération, inventaire, une ligne
  par fichier (état, motif, secondes, analyses), doublons, reprises de budget mémoire,
  organisation, vérification. Si le journal ne peut pas s'écrire, le rapport affiche
  `Journal incomplet : <raison>`.
- **Isolation** : une exception d'un lecteur ou d'un worker marque **sa** ligne en `error`
  avec son message ; l'opération continue. C'est `safe_parse` / `_future_documents`.
- **Comptes justes** : `report['summary']` est calculé une fois depuis les lignes affichées ;
  le bandeau de l'onglet Imports le cite, compte les doublons et ajoute la vérification.

## 3 bis. Le reste de la 0.5.1

- **Arbre lisible** : `core/artifact_names.py` traduit un chemin en type de preuve
  (`Event logs · Security`, `Amcache`, `Browser history`, `Browser cookies`, `Prefetch`,
  `MFT`, `NTUSER.DAT`, `Jump lists`…), sinon le nom du dossier en sautant la plomberie
  (`Saved_Files`, `C:`, `Users`, `AppData`, le nom du profil). Deux entrées identiques sont
  séparées par le nom du fichier puis par un numéro. Le chemin complet reste en infobulle et
  dans le rapport. Utilisé par `ui/navigation.py` (feuilles **et** nœuds de collecte) et par
  le nom enregistré d'une collecte (`start_workflow`).
- **Démarrage** : l'ident garde ses **6,5 s** (choix de l'utilisateur, 18 nov. : « je veux
  qu'elle dure toujours 6,5 secondes ») et devient le **plancher** du lancement, pas un ajout.
  Mesuré sur la VM : fenêtre construite en **0,32 s** (import Qt compris) ; `reveal_delay()`
  ne rend la main qu'à la fin de l'ident, et rend **0** si la construction a dépassé les 6,5 s.
  Le lancement vaut donc max(6,5 s, construction), au lieu de construction + 6,5 s.
- **Livraison en dossier zippé** : l'exe `--onefile` de 281 Mo se décompressait dans `%TEMP%`
  à **chaque** lancement — mesuré **43 s** pour afficher `--help` sur la VM (disque lent +
  Defender qui scanne chaque DLL extraite), contre 0,9 s depuis les sources. La construction
  passe en `--onedir` et publie `Fireblade-<version>-win64.zip` : on décompresse une fois, le
  lancement ne paie plus l'extraction. Chaîne touchée : `scripts/windows/build.py`,
  `verify.py` (copie le dossier, exige `packaging == 'onedir'`), `bundle.py` (l'étiquette),
  `validation/windows_check.py`, `scripts/release.py` (l'asset est le zip, empreinte dans le
  corps de la release), `update_release_readme.py` (choisit l'archive), le workflow
  (`--asset dist`, chemins `dist/Fireblade/Fireblade.exe`) et les deux tests de release.
- **Assistant** : rien ne se télécharge sans un clic sur `Set up the local model…` (vérifié :
  `install_model`/`install_runtime` ne sont appelés que par ce bouton). Le texte d'un modèle
  absent ne ressemble plus à une panne ni à une tâche à faire.

## 3 ter. Pack de démonstration publié

- **`test-pack-v2`** : `Fireblade-Sample-Collection-2026-11-18.zip`, 5 606 171 o,
  SHA-256 `b3482b9bcc393e6bcdc2b2900b7128268596a6624e1c0d7bcca6f25031d7e4e7`.
  Contenu réel pris sur la VM : 183 journaux EVTX, Amcache, 60 Prefetch, 251 tâches
  planifiées, historique PowerShell, `inventory.json` (497 fichiers), README.
- Retirés avant publication, et pourquoi : `SAM`/`SECURITY` (empreintes et secrets LSA),
  `SOFTWARE`/`SYSTEM`/`NTUSER.DAT`/`UsrClass.dat`/`WebCache` (identité machine, profil
  réseau, fichiers récents), `Security.evtx`/`SRUDB.dat` et les canaux NTLM, SMB, OpenSSH,
  LiveId, PushNotification (adressage du labo, jeton de notification).
- Balayage avant zip : motifs de clés, clés privées, jetons cloud, `192.168.1` — aucun hit
  dans ce qui reste. Le zip a été retéléchargé depuis l'URL publique et son empreinte
  comparée avant d'être annoncé.
- Publié depuis la **tour** (`gh` y est authentifié, scope `repo`), asset par asset, en
  prerelease comme les packs v1. Le README de `main` le cite en tête des jeux de données.
- **Aucune clé GitHub utilisable ailleurs** : ce que `~/.hermes` contient est un motif de
  test (API 401), la VM n'a qu'une clé SSH de dépôt, et `git@github.com` est refusé depuis
  le conteneur. Toute publication passe par la tour, réveillée par WoL.

## 4. Décisions prises, à ne pas rouvrir sans raison

- **Le doublon est décidé par l'empreinte de la source**, jamais par le nom ni la date :
  c'est le seul identifiant défendable devant un rapport.
- **Une collecte disque ne déduplique pas** : deux partitions aux mêmes octets sont deux
  artefacts, avec deux localisations. Le test `test_complete_mbr_disk_exposes_both_partitions`
  le pin (2 analyses).
- **L'index des doublons est par case** (`Collectes/import-index.json`) : la même preuve
  importée dans deux cases est lue deux fois, et c'est ce que ces deux cases demandent.
- **Une opération interrompue n'est jamais reprise automatiquement** : l'interface propose,
  l'analyste décide. Rien ne relit un dossier sans un clic.
- **Le journal ne fait jamais échouer l'import**, mais il le dit : un import sans journal
  complet n'est pas présenté comme complet.
- **La vérification n'est pas optionnelle** : elle ouvre chaque analyse, à la fin de
  l'opération. Coût mesuré sur la recette, à comparer au total de la collecte.
- Le regroupement par défaut reste le SQL ; l'assistant local (0.5.0) est inchangé.

## 4 bis. Publier (fait pour la 0.5.0, à refaire à l'identique)

- La VM **pousse en SSH** : clé `C:\Users\fb\.ssh\id_ed25519` (`fireblade-vm@proxmox`, type
  authentification), remote `git@github.com:23R0534ZXT/kagarasu.git`. Aucun jeton n'est
  stocké sur la VM ; `GIT_SSH_COMMAND='ssh -o BatchMode=yes -o StrictHostKeyChecking=no'`.
- La CI construit l'exe et publie la release **sous `github-actions[bot]`** : la recréer depuis
  la tour (`gh` y est authentifié) — `gh release download`, `gh release delete`, `gh release
  create` avec le même exe et le même corps. Le corps contient déjà `Commit:` et
  `SHA-256 of Fireblade.exe:` : vérifier que le fichier téléchargé donne la même empreinte.
- **Le titre doit être posé par l'API en UTF-8 brut** : `gh api --input` et PowerShell
  ré-encodent, et le tiret cadratin devient `ÔÇö`. Utiliser `urllib` avec
  `Content-Type: application/json; charset=utf-8` et le jeton rendu par `gh auth token`.
- Le workflow a ensuite committé lui-même la mise à jour du README (lien direct vers l'exe et
  vers le run de qualification) : ne pas la réécrire, rebaser dessus.
- Une prerelease laisse `latest` sur la version précédente ; le lien du README vise donc le
  tag, pas `/releases/latest`.
- **Ne pas pousser sans demande explicite dans la session** : préparer la fusion et le tag,
  annoncer l'état, demander.

## 5. Pièges rencontrés cette nuit

- **`duplicate_of` se déclenchait sur le fichier lui-même pendant une reprise** : `first is
  not None` au lieu de `first is not entry`. La carte des empreintes doit se remplir avec
  `setdefault(digest, entry)`, sinon un fichier relu se croit le doublon de lui-même et la
  reprise ne réécrit rien (documents vides, statut `duplicate`).
- **La racine commune des sources** (`common_root`) est ce dont les libellés se mesurent, pas
  ce dont la sortie doit être exclue : un dossier de travail posé à côté d'un **fichier**
  sélectionné est légitime, seul un dossier source peut avaler sa propre collecte.
- **Le rendu fusionné n'est pas une source** : `organize()` remplace `documents` ; une
  reprise doit restaurer `raw_documents` avant de relancer, sinon `organize` refuse
  (« Provenance de résultat absente »).
- **Les pilotes de recette patchaient le sélecteur par son ancien nom** : `s1`, `s2`, `s4`
  et deux tests d'interface utilisaient `choose_collection_directories`. Les renommer tous
  (`choose_import_sources`), sinon `AttributeError` au premier import de la section.
- **Un test isolé qui échoue en français n'est pas une régression** : les trois tests de
  `preview_text` de `tests/ui/test_collection_report_actions.py` échouent seuls sur `main`
  aussi (la langue est posée par un autre test dans la suite complète). Prouvé avec un
  `git worktree` sur HEAD, puis clos.
- **La vérification après import ouvrait DuckDB sur les analyses en cours d'écriture** : elle
  tourne après `organize`, quand plus aucune transaction n'est ouverte.
- Le disque de la VM reste juste après une collecte 10 Gio : `Get-PSDrive C` avant chaque
  recette ; les cas de test pèsent ~20 Go chacun.

- **Une copie locale de `app.py` avait été laissée par une session précédente** : la patcher
  aurait installé un fichier d'il y a deux jours. Toujours `scp` le fichier à modifier juste
  avant de le patcher, et comparer les empreintes quand un doute existe (`md5sum`).
- **Un `\U` dans une docstring** (`C:\Users\...`) casse le module à l'import : écrire la
  docstring en `r"""…"""` ou éviter le chemin en dur.

- **Construire le dossier sur la VM demande trois réglages d'environnement** : le SDK .NET
  10 décompressé dans `C:\Users\fb\tools\dotnet` avec `FIREBLADE_DOTNET`, son dossier
  ajouté au `PATH` (car `build_forensic_tools` appelle `dotnet` par son nom), et
  `C:\Users\fb\tools\git\cmd` au `PATH` (une session SSH n'a pas git). Sans l'un des
  trois, le build meurt en `WinError 2` après avoir déjà construit les hôtes .NET.
- **L'auto-test du produit exigeait un exe seul dans son dossier** : la vérification d'un
  bundle `--onedir` échouait sur « Le programme a besoin de fichiers à côté du .exe. ».
  L'assertion accepte maintenant l'exe et `_internal`, et rien d'autre — c'est la même
  promesse, dite pour un dossier.

## 6. Vérifier

```powershell
# sur la VM, dans C:\Users\fb\dev\fireblade
powershell -File C:\Users\fb\vm_gate.ps1                    # ~16 min, doit finir TOUT EST VERT
powershell -File C:\Users\fb\vm_section.ps1 -Name s1_import
powershell -File C:\Users\fb\vm_section.ps1 -Name s17_import_051
```

Recette complète : `tools/recette.sh` depuis Proxmox enchaîne `s0` à `s17` et écrit
`recette-report.txt`. Journal détaillé et captures : `C:\fireblade-test\harness\journal.json`,
`C:\fireblade-test\shots\`.

Contrôles de l'import, sans interface :

```powershell
.venv\Scripts\python.exe -m pytest -q tests/core/test_import_operation.py
```

## 7. Ce qui reste ouvert

1. **Deux collectes d'un même case ne se fusionnent pas** : chaque import garde son dossier,
   son journal et son rapport. Un rapport unique par case demanderait une décision de produit.
2. **Qualité du modèle** (0.5.0) : MiniCPM5-2B donne un résumé utile mais pauvre ; limite du
   modèle, pas du garde-fou.
3. **Enquête multi-étapes** : l'assistant explique un constat, il ne conduit pas l'analyse.
4. **`vc_redist`** à intégrer proprement au programme d'installation.
5. Sujets 0.4.2 toujours ouverts : guides en français, `docs/validation` embarqué dans
   l'exe, résidu de traduction « exports ».
6. **Chemins de plus de 260 caractères** : toujours le seul cas connu où un fichier peut
   échapper à l'inventaire ; à provoquer sur la VM avant de promettre le contraire.
