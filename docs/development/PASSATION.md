# Passation — état du projet

Document de reprise, mis à jour en fin de session. Il dit où en est le code, ce
qui a été décidé, et ce qui reste. Le détail technique vit dans le skill
`fireblade-verification` ; ce fichier est la vue d'ensemble.

Dernière mise à jour : 16 novembre 2026. La 0.4.0 est prête à publier.

## Où en est le projet

- **Version 0.4.0, prête à publier** : le lot est empilé sur la branche `hermes/0.4.0`
  (26 commits devant `main`), porte verte sur l'arbre exact. `main` local est à
  `5f6f5c9`, `origin/main` à `6c05c22` : **rien n'est poussé**. La fusion, le tag
  `v0.4.0` et le push attendent l'accord explicite du mainteneur ; ensuite la CI
  construit et vérifie l'exe, et `publish-qualified` le publie avec son compte.
- La **0.3.1** reste téléchargeable : `Fireblade.exe`, 280 508 600 octets,
  SHA-256 `0b4f94676861da3ed15d65291f20f37ff781a2b8d0d7517ced725e42d2203a1a`,
  publiée le 6 novembre 2026.
- **Vérification de référence** de la 0.4.0 : voir la section « Vérification » du
  bas de ce document, remplie avec le résultat du dernier passage de la porte.

## Ce qui a été livré dans la 0.4.0

- **Onglet Imports actionnable** : aperçu du fichier (texte, repli cp1252, hexadécimal),
  copie des non traités (copie, jamais déplacement), export CSV de la vue filtrée,
  mise à l'écart réversible, suppression protégée par le SHA-256 relevé à la collecte,
  colonne « Motif », compteurs avec les écartés, décisions persistées dans `collection.json`.
- **Lecteur à la demande** (`Collection.analyse_single(path, reader)`) : relancer un
  fichier non reconnu avec le lecteur choisi, l'importer comme une source, ouvrir
  l'analyse. Le hash de référence est celui de la collecte ; à défaut, la première
  lecture le fixe, et une lecture suivante est refusée si le fichier a changé.
- **`core/textreader.py`** : texte et pages HTML sans aucune dépendance — une ligne
  par ligne, horodatage gardé seulement s'il ouvre la ligne, liens collectés, octets
  invalides conservés, binaire refusé.
- **`core/pdfreader.py`** : couche texte seulement, page par page, via `pypdf`
  (extra optionnel, épinglé dans `requirements/runtime.txt` pour l'exe). Pas d'OCR :
  un PDF sans couche texte est signalé et compté avec les avertissements.
- **Générique de démarrage** redessiné (`ui/startup.py`) : plus de GIF, tout est peint,
  6,5 s, déterministe ; quatre tests de rendu le vérifient.
- **Espace de travail** : les trois modes gardent les mêmes barres et la barre d'onglets,
  les panneaux détachables reviennent dans le même état, et un onglet cliqué sort du mode.
- **Fenêtre de collecte** : deux questions séparées (travailler pendant le parsing, puis
  disposition par artefact ou vue unifiée), libellés en anglais, chaque option expliquée.
- **Porte** : suite lancée en UTF-8 (les fixtures écrivaient en page de code locale),
  purge des dossiers `%TEMP%\pytest-of-…` périmés (casse du chemin), et le test
  « le cœur ne charge pas Qt » garde désormais les paquets de l'interpréteur.
- **Dossiers en parallèle** : un dossier est analysé sur plusieurs fichiers à la fois,
  fusionnés dans l'ordre du fichier ; les ouvriers voient l'annulation par copie du
  contexte, et le thread qui tient le bilan l'honore aussi entre deux fichiers.
- **Import en un passage** : lecture du fichier entier tant qu'il tient dans une
  transaction — 3,65 Go en 69 s au lieu de 148 s, 59 s à chaud, mémoire inchangée
  (pic 1 077 Mo pour un budget de 1 Go), repli en tranches au-delà du seuil et sur
  manque de mémoire.
- **Threads automatiques par défaut** : la sentinelle `0` est résolue avant le moteur,
  libellé « Automatique » dans Préférences → Ressources, aide mise à jour.
- **Comparatif Timeline Explorer** re-mesuré sur les cinq tailles :
  `docs/development/BENCHMARK-0.4.0.md` — Fireblade passe devant à toutes les tailles
  tout en restant à son budget.

## Ce qui a été livré dans la 0.3.1

- **Toute l'interface est traduite**, plus seulement les menus : dialogues,
  gestionnaire de colonnes, préférences, chasse IOC, couverture, chronologie,
  en-têtes de tableaux, listes, infobulles, textes de saisie, messages d'état.
- **Les textes calculés à l'affichage** passent par la même table, au moyen de
  gabarits (`Analyse absente : {}`). Compteurs, fins de tâche et erreurs
  affichées sont donc traduits eux aussi.
- La couche de langue agit **à l'ouverture d'une fenêtre** (parcours de l'arbre
  de widgets) et **au moment où le code écrit le texte** (accroches sur les
  setters Qt : `setText`, `setPlaceholderText`, `addItem`, `setTabText`,
  `setHorizontalHeaderLabels`, `showMessage`, `setWindowTitle`…).
- **Notes de sélection** : `window.selection_note()` dit combien de lignes sélectionnées portent déjà une note et si elles partagent la même ; le menu bascule entre « Ajouter » et « Éditer », et l'édition pré-remplit la note commune.
- **Notes de cellule** : la table `bookmarks` porte maintenant `(row_id, column_id, note)`, `column_id = -1` restant la note de ligne. Une note par cellule, éditable, avec fond vert et infobulle ; `engine.cell_notes()` les lit, `GridModel.cell_notes` les expose. Les analyses plus anciennes sont migrées à l'ouverture (`migrate_bookmarks`) et `analysis_storage` accepte les deux schémas. L'export CSV des annotations ne contient que les notes de ligne.
- **Double-clic sur une cellule = afficher la cellule** (texte, JSON, XML), plus jamais la note : demande explicite du mainteneur. La note et le signet passent par le menu Édition ou un clic dans la première colonne. Les guides (fr et en) ont été mis à jour en conséquence.
- Les **cinq guides intégrés** existent en anglais (`*-en.md` à côté de l'original) et `guide_path()` choisit selon la langue ; `tests/test_guides.py` vérifie que chaque guide a sa version anglaise et garde la même structure.
- Le français reste intégral : chaque libellé source est mémorisé, le retour au
  français restitue le texte d'origine.
- Six chaînes ne sont pas traduites et ne doivent pas l'être : des noms de
  fichiers d'exemple (`évidence.csv`, `résumés.csv`, `fonctions étendues.csv`)
  et deux expressions TLE synthétiques. Ce sont des données.

## Comment la traduction est outillée

- `src/fireblade/core/i18n.py` — la table `EN` (860 entrées), les gabarits à
  `{}`, `translate()` (affichage), `english()` (forme de référence),
  `has_english()` (une chaîne est-elle couverte).
- `src/fireblade/ui/language.py` — `translate_tree()` (un sous-arbre entier),
  `LanguageFilter` (traduction au `Show`, installé par `install(app)`),
  `install_hooks()` (traduction à l'écriture), `source_of()` (mémoire du libellé
  source, rafraîchie quand le code remplace le texte).
- `scripts/i18n_inventory.py` — mesure la couverture : `--missing`,
  `--by-file`, `--write-baseline`.
- `scripts/i18n_merge.py` — écrit un lot de traductions après vérification des
  clés exactes, des `{}` et des doublons.
- `tests/test_translation_coverage.py` et `tests/data/untranslated_french.txt` —
  deux garde-fous : aucune nouvelle chaîne non traduite, et la liste des
  reliquats ne peut que diminuer. Un troisième test lit la vraie fenêtre en
  anglais et échoue sur tout mot français visible.

## Plan de la 0.5.0

Les quatre points du plan 0.4.0 sont traités : points d'entrée grisés sans case,
chronologie en place, exe et pont .NET vérifiés par la CI, suite complète en CI.
Ce qui reste ouvert pour le lot suivant :

1. **Import cp1252** : un CSV exporté par Excel en Europe de l'Ouest lève encore un
   `UnicodeDecodeError` parce que l'import par défaut est UTF-8 strict. Le sélecteur
   d'encodage existe côté interface ; reste à décider si le défaut doit détecter et
   basculer, avec avertissement (changement de comportement = son propre test).
2. **PDF** : un aperçu du nombre de pages et de la couche texte dans le bilan, et
   l'extraction des métadonnées (auteur, dates) — pas d'OCR, décision tenue.
3. Ce que le mainteneur demandera ; un commit par ajout, porte verte à chaque étape.

### Traité dans la 0.4.0

- « Parser un dossier » exige un case : les points d'entrée restent visibles mais
  **grisés** sans case, infobulle « Open or create a case first. » ; la création
  automatique du case au passage est écartée.
- Chronologie : table + bandeau d'ensemble + vue graphique, en place.
- Exe et pont .NET vérifiés à chaque build par la CI : 47 contrôles isolés
  (`scripts/windows/verify.py`), self-test, `plugin_checks`, `legacy_plugin_checks`,
  lecteur TLE public épinglé, matrice de lecteurs amont. Pas de SDK .NET sur le
  poste : c'est la CI qui les fait tourner.
- Couverture CI étendue : le job `tests` lance la suite complète. Reste hors de
  portée du poste : Q01/Q04–Q08 (comparaison avec une vraie Timeline Explorer,
  essais humains).

## Publication des releases

Le mainteneur veut que la release soit publiée **avec son compte**, pas avec le
bot de la CI. Deux façons, dans cet ordre :

1. Ajouter un secret `RELEASE_TOKEN` (jeton personnel, portée `contents: write`)
   au dépôt : le job `publish` l'utilise en priorité, et la release suivante est
   signée à son nom sans rien faire de plus.
2. Sans ce jeton, la CI publie en `github-actions[bot]`. On corrige après coup :

```bash
gh release view vX.Y.Z --json body -q .body > body.md
gh release delete vX.Y.Z --yes              # le tag est conservé
gh release create vX.Y.Z --title "<titre>" --notes-file body.md "<exe vérifié>#Fireblade.exe"
```

   L'exe doit être celui déjà vérifié (même SHA-256) : on réutilise le fichier
   téléchargé, jamais une reconstruction.

## Décisions prises, à ne pas rouvrir

- L'application reste en **Qt** ; les maquettes HTML n'ont servi qu'à valider des
  structures.
- Les qualifications Windows (visuelle et 3 GiB) **fixent la langue du profil
  qu'elles créent** à `fr` : elles décrivent l'interface française.
- La suite de tests ne doit jamais pouvoir se figer sur une boîte modale ; un
  garde-fou les rejette et les nomme.
- Les dates sans fuseau sont lues comme **UTC** depuis la 0.2.3.
- **Les textes dynamiques sont traduits** eux aussi : la 0.3.1 ne s'arrête pas
  aux libellés statiques.
- **Six chaînes de données restent en français** (noms de fichiers d'exemple,
  expressions TLE) : les traduire serait faux.
- **Deux langues seulement** : anglais (référence) et français. La table reste
  une paire de dictionnaires ; une troisième langue ne demanderait pas de refonte.
- **À partir de la 0.3.2, on ne travaille plus que l'anglais.** Les nouveaux
  libellés s'écrivent directement en anglais dans le code. Le français déjà
  traduit reste affichable et ne casse rien, mais il n'est plus maintenu : une
  nouvelle chaîne n'a pas à recevoir d'entrée française, et la couverture du
  français n'est plus vérifiée. La mesure de couverture et les tests de garde
  restent utiles pour l'anglais seul (aucun texte codé en dur ne doit s'afficher
  brut dans une fenêtre anglaise).

## Pièges connus

- Ne jamais lancer deux suites de tests en parallèle : DuckDB prend un verrou
  d'écriture et la seconde bloque sans rien afficher.
- `kill` sur une session de terminal ne tue pas le processus pytest enfant ; il
  faut tuer par PID, sinon les verrous restent.
- Une fenêtre de test pilotée par type (`findChild`) casse dès que la fenêtre est
  restructurée : passer par ses méthodes.
- **Esperluettes des titres d'onglets** : Qt lit `&` comme un raccourci, on
  échappe en `&&` pour l'affichage, mais il faut mémoriser le libellé **non
  échappé**, sinon chaque passage double les `&` (`Timeline &&&& correlations`).
- **Ne pas réécrire un texte inchangé** : `setTabText` déclenche un relayout
  complet de la barre d'onglets. Une passe de langue qui réécrit chaque onglet
  fait passer un fichier de tests de 38 s à plus de 20 min.
- **Un menu ouvert en popup est sa propre racine** : `findChildren` ne le renvoie pas, donc ses entrées n'étaient jamais traduites — même piège pour une `QTabBar` posée comme racine.
- **Les guides sont empaquetés par dossier** (`docs/guides` → `resources/docs/guides`) : une liste écrite à la main laissait les versions anglaises hors de l'exe.
- Les accroches Qt sont installées **une seule fois** et ne font rien quand la
  langue est le français : c'est ce qui garde la suite rapide.

- **Un dossier `%TEMP%\pytest-of-<utilisateur>` périmé change la casse des chemins** :
  pytest calcule le nom en minuscules, Windows réutilise le dossier existant sans
  corriger son orthographe, et `resolve()` renvoie la casse du disque. Les tests qui
  comparent des chemins échouent alors sans rapport avec la cause. La porte purge ces
  dossiers (`purge_stale_pytest_tmp()`), et les comparaisons passent par `os.path.normcase`.
- **La suite doit tourner en UTF-8** (`PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`) :
  beaucoup de fixtures écrivent leurs CSV sans `encoding=`, donc en page de code
  locale sous Windows, alors que le code lit en UTF-8 et que la CI est en UTF-8.
- **Une annulation demandée pendant une collecte parallèle** peut arriver alors que
  l'ouvrier a déjà fini : aucun `OperationCancelled` n'est levé, et la collecte finit en
  `complete`. Le thread qui fusionne doit vérifier l'arrêt avant de publier le fichier
  suivant (sans quoi un run sur dix passe et le suivant échoue). Une course se prouve par
  25 répétitions, jamais par un run vert.
- **`SET threads=0` est refusé par DuckDB** et l'import échoue alors sans message : toute
  valeur « automatique » doit être résolue avant le moteur, en un seul endroit.
- **`duckdb.InterruptException`** est ce que lève une lecture interrompue : sans
  conversion en `OperationCancelled`, une collecte annulée se termine en `complete`.
- **Le lanceur `.venv\Scripts\python.exe` démarre de nouveau** sur la tour (la jonction
  `%APPDATA%\uv\python\…` a été reconstruite), et la porte passe par
  `powershell -File C:\Users\23R\gate.ps1` — `dev_check --quick` pour le rapide, `-Full`
  pour la suite entière. S'il cesse de démarrer (`os error 448`, trampoline uv), c'est la
  jonction : la reconstruire, pas contourner. Traiter les scripts `.ps1` comme
  ASCII seulement, et ne jamais piper un long run (écrire dans un journal et le relire).

## Vérification

- Dernier passage de la porte pour la 0.4.0 : **1 434 tests passés, 28 ignorés**,
  plateforme Qt Windows, fenêtre réelle construite, ruff propre — via
  `powershell -File C:\Users\23R\gate.ps1 -Full`, sur l'arbre exact du dernier commit
  de la branche (deux passages verts de plus en cours de route : 1 431, puis 1 434).
- Mesures de la 0.4.0 sur le fichier de 3,65 Go (i7-12700K, budget 1 Go) : import
  **69 s** (59 s à chaud), pic mémoire **1 077 Mo** mesuré de l'extérieur, 32 millions
  de lignes relues et identiques, recherche de cinq motifs en 5,8 s.
- Sondes hors suite, sur fichiers réels : 46 contrôles (texte UTF-8/cp1252/UTF-16/BOM,
  page HTML cp1252 et déclarée, PDF d'une et trois pages, PDF chiffré, PDF tronqué,
  arborescence de collecte complète) — 46 sur 46. Journal de 100 000 lignes importé en 1,5 s.
- Les échecs de la suite locale venaient tous de la porte elle-même : 25 par
  encodage, 7 par casse du dossier temporaire, 1 par `PYTHONPATH` réduit, puis 2 par
  le garde-fou de fenêtres modales qui rejetait un dialogue en cours de saisie. Aucun
  n'était un défaut du produit.

## Comment reprendre

Premier message d'une nouvelle session, suffisant pour repartir :

> Fireblade 0.4.0, branche `hermes/0.4.0` prête et verte, rien de poussé. On ne
> travaille qu'en anglais. Charge le skill `fireblade-verification` et lis
> `docs/development/PASSATION.md` ; la tour Windows est en SSH sur `23R@192.168.1.167`,
> le dépôt dans `C:\Users\23R\dev\fireblade`, et la porte tourne par
> `powershell -File C:\Users\23R\gate.ps1 -Full` (compte ~8 min, `TOUT EST VERT`).

Le reste — historique, décisions, conventions — se trouve dans le dépôt et dans
la mémoire persistante.
