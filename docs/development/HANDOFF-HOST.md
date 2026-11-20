# Reprise du portage — Fireblade Host

État au 20 novembre 2026, 15h45. Ce texte suffit pour reprendre le chantier
depuis une session neuve.

## Où en est le code

- Branche `feat/host-edition`, **39 commits** au-dessus de `main`. `main` n'a
  jamais été touchée : rien n'est publié, rien n'est poussé.
- Dernier commit : `f1d95d4 Host: the graph as a PNG`.
- **Porte de vérification verte sur la branche** : `1752 passed, 28 skipped`,
  ruff propre, `TOUT EST VERT`, exit 0 (17 min 23 s) — lancée sur la VM Windows
  après le commit de la disposition de colonnes.
- Image `fireblade:host` construite et **saine** sur `http://192.168.1.201:8095`
  (`{"status":"ok","version":"0.7.9","cases":8}`).

## Travail en cours, non commité, non vérifié

Une passe a écrit le **backend de l'aperçu d'import** puis s'est arrêtée avant
de construire et de tester. Il est dans la copie de travail
`/root/fireblade-web`, pas sur la VM, pas dans git :

- `src/fireblade/web/service.py` : `preview_source(self, source)` (vers la ligne 724) ;
- `src/fireblade/web/server.py` : `POST /api/cases/{identifier}/preview` et
  `POST /api/cases/{identifier}/preview-upload` (vers les lignes 115-140).

À faire dessus, dans cet ordre : lire le code, le terminer, construire l'image,
appeler les deux routes sur un vrai fichier, vérifier que le profil renvoyé est
celui de `fireblade.core.profiles.detect_profile`, puis brancher l'interface
(avant validation d'un import, afficher colonnes + profil + mapping) et
seulement ensuite commiter. **Ne pas commiter ce travail en l'état.**

## Ce qui est fait et vérifié dans le navigateur

Neuf onglets comme le desktop : Analyses, Imports, Cases, Chronologie, Chasse
IOC, Hayabusa + AI, Actions & suivi, Attack graph, Détection EVTX.

- **Grille** : ouverture d'analyse, pagination, tri simple et multi-colonnes,
  filtres par colonne avec opérateurs, filtre avancé ET/OU/NON (un groupe plat),
  groupement par colonne, intervalles de dates, descente dans un groupe,
  signets, notes de ligne et de cellule, règles de coloration (dont création
  depuis une cellule), colonnes masquées / épinglées / redimensionnées
  enregistrées dans l'analyse, affichage booléen, colonnes dérivées, vues
  nommées, export CSV, copier la ligne, afficher la cellule entière.
- **Import** : par le navigateur, par glisser-déposer, par chemin serveur ; trois
  dispositions (par fichier, par famille d'artéfacts, grille unique) ; historique
  par fichier avec le lecteur utilisé et la raison d'un échec ; treize lecteurs
  .NET qui tournent sous Linux via `dotnet`.
- **Cases** : création, renommage, destruction avec certificat DoD (3 ou 7
  passes), archivage avec libération d'espace, restauration, export/import d'un
  case portable `.fireblade`.
- **Chronologie**, **chasse IOC** avec chasses enregistrées (rejouables),
  **Hayabusa** avec niveaux, **graphe d'attaque** avec export ATT&CK Navigator
  et export PNG, **rapport client** HTML, **suivi d'actions**, **recherche
  globale**, **préférences** (inventaire des lecteurs), **affichage** (taille de
  texte, hauteur de ligne, palette du desktop).

## Ce qui reste

1. Terminer et vérifier l'aperçu d'import (voir ci-dessus).
2. Groupes de filtres **imbriqués** dans le dialogue Advanced filter : le noyau
   accepte des arbres plus profonds que le groupe plat actuel.
3. Reprendre `docs/development/HOST-PARITY.md` groupe par groupe : cocher ce qui
   est couvert, traiter ce qui reste utile, déclarer explicitement le reste.
4. Porte complète sur la branche, puis documentation (`HOST-EDITION.md`,
   `HOST-PARITY.md`, `RELEASE-NOTES.md`) et préparation du lot.
5. Ne pas oublier la **version Windows** : elle reste la référence publiée.

## Hors périmètre, à déclarer et non à coder

- « Afficher dans l'Explorateur », ouvrir le dossier parent : il n'y a pas
  d'explorateur système derrière un navigateur.
- Détacher un panneau, dispositions de fenêtres, barres d'outils flottantes :
  gestion de fenêtres de bureau ; le web obtient le même résultat par les
  dialogues Group… et Columns….
- **L'IA n'est pas branchée** : aucun endpoint, aucune clé, aucun appel
  sortant. L'onglet de détection le dit. La décision (modèle local dans le
  conteneur ou API distante) appartient à l'utilisateur et change ce qui peut
  sortir du serveur.
- Forcer un profil CSV à l'import demanderait une évolution du **noyau**, donc
  des deux éditions à la fois : `detect_profile` vit dans la mise en page
  automatique et les préférences, il n'existe pas de paramètre de forçage dans
  le chemin d'import. À décider, pas à improviser.

## Environnement de travail

- Copie de travail locale de l'agent : `/root/fireblade-web` (pas un dépôt git :
  c'est un miroir synchronisé par `scp`).
- Dépôt réel : VM Windows `fb@192.168.1.80`, `C:/Users/fb/dev/fireblade`, git
  dans `C:/Users/fb/tools/git/cmd/git.exe`.
- Porte complète : `.\.venv\Scripts\python.exe -m scripts.dev_check` sur la VM,
  ~17 min, doit finir par `TOUT EST VERT`.
- Docker : `root@192.168.1.201`, image `fireblade:host`, conteneur
  `fireblade-host`, port `8095:8080`, volume `/srv/fbcases:/data/cases`.
- Boucle de build : copier `src/fireblade/web` dans `/root/fbctx/src/fireblade/web`,
  `tar` + `scp` vers `192.168.1.201:/root/`, extraire dans
  `/opt/fireblade-build`, `docker build -q -t fireblade:host`, puis
  `docker rm -f fireblade-host` et
  `docker run -d --name fireblade-host -p 8095:8080 -v /srv/fbcases:/data/cases fireblade:host`.
  Un build prend 4 à 5 minutes : le lancer en tâche de fond et travailler
  pendant ce temps.
- Cases de test : `e3253c49ca6848458e28d07642fa9423` (démo, 480 lignes),
  `2a7afd0b938e4f53a9be2018bab5e16b` (EVTX, 1 327 lignes),
  `3993410bbd4d45338f932f4554afaa93` (Security.evtx, pivot processus).

## Règles

- Jamais de push sur `main` ; tout reste sur `feat/host-edition`.
- Interface en **anglais uniquement**.
- Commits signés `23R0534ZXT <112427500+23R0534ZXT@users.noreply.github.com>`,
  message en anglais disant pourquoi et ce qui a été vérifié.
- Ne pas toucher à `src/fireblade/ui/` (le desktop Qt) sans accord explicite.
- Aucune IA branchée, aucun appel sortant.
- Une fonctionnalité n'est « faite » que vérifiée dans un vrai navigateur
  (capture à l'appui) ou par un appel API réel.

## Pièges déjà payés

- Les fichiers édités depuis Linux arrivent en LF : git sur Windows prévient que
  LF deviendra CRLF, c'est normal, ne pas « corriger ».
- Vérifier après chaque build : un `docker build` réussi ne dit pas que le
  conteneur sert le bon code, il faut appeler `/health` puis l'endpoint touché.
- `findstr` sur Windows renvoie aussi les tests quand on cherche un libellé :
  chercher dans `docs/development/PARITY.md` (colonne « declared in ») pour
  retrouver le module d'origine.
- Archiver un case qui contient encore des preuves originales est **refusé** par
  le noyau (c'est voulu) ; restaurer crée un **nouveau** case, l'archive restant
  la copie conservée.
- Le certificat de destruction est du HTML sauf cible `.pdf` : l'écrire en
  `.html`, hors du dossier du case.
- Pivot : refuser un jeton JSON (bruit EvtxECmd) et retomber sur un chemin
  d'exécutable trouvé dans n'importe quelle cellule.
