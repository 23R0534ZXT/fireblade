# Passation — état du projet

Document de reprise, mis à jour en fin de session. Il dit où en est le code, ce
qui a été décidé, et ce qui reste. Le détail technique vit dans le skill
`fireblade-verification` ; ce fichier est la vue d'ensemble.

Dernière mise à jour : 17 novembre 2026. **La 0.4.2 est prête à publier.**

## Où en est le projet

- **0.4.1 publiée.** `Fireblade.exe`, 281 209 660 octets, SHA-256
  `14ae688b…`, sous le compte du mainteneur. `main` local et `origin/main` sont
  au même commit, `32c84e3`.
- **0.4.2 prête, non poussée.** Branche `hermes/0.4.2`, **9 commits devant
  `main`**, porte verte sur l'arbre exact (1 459 passés, 28 ignorés, ruff propre,
  fenêtre réelle). La fusion, le tag `v0.4.2` et le push attendent l'accord
  explicite du mainteneur ; ensuite la CI construit et vérifie l'exe.
- Rien n'est poussé, aucune release n'est touchée depuis la 0.4.1.

## Ce que contient la 0.4.2

**La vitesse** — la même collecte de 9,74 Gio passe de 50 min 49 s à 6 min 0 s :
lecture de chaque fichier dans son propre processus, un gros fichier découpé en
tranches alignées sur les lignes (CSV recollés à l'identique), et la provenance
écrite par l'import au lieu d'être recopiée ligne à ligne.

**Les corrections de la recette** (six défauts réels, chacun avec son test) :

- l'audit de couverture ne retournait plus en silence : il démarre seul dès que la
  requête en cours libère la fenêtre ;
- la colonne Motif du bilan n'est plus vide : le motif remonte du run, du membre ou
  de l'avertissement ;
- l'export des annotations ne livre plus un fichier à en-tête seul : il refuse et
  donne le compte ;
- les libellés français visibles (neuf entrées, plus « drive error » corrigé en
  « reader error », plus les statuts traduits là où ils sont insérés) ;
- les champs de filtre de colonne annoncent leur colonne au lieu d'un numéro ;
- le refus d'un fichier Timeline Explorer dit quel fichier et quoi faire.

**Le reste** : la colonne Read type écrit `Structured`/`Raw` (les anciennes
analyses françaises restent lisibles et comptées), et une déclaration Zeek n'est
plus comptée comme une ligne brute.

## La recette de la 0.4.1, ce qu'elle a donné

Passée sur une **VM Windows 11 neuve** (la tour ne peut pas exécuter les outils
.NET : Smart App Control bloque `EvtxECmd.dll` et RECmd ne revient jamais).

- **8 sections, 286 étapes : 274 OK, 1 à revoir, 7 échecs.**
- 145 captures, toutes relues.
- Les échecs ont donné six défauts réels, tous corrigés et vérifiés.
- **Deux constats étaient faux et sont rectifiés** dans les constats de recette :
  « la barre d'état affiche Prêt en anglais » (les captures anglaises disent
  `Ready` ; j'avais lu la capture en français) et « le résumé et le tableau ne
  comptent pas pareil » (199 + 23 + 1 + 4 = 227, tout concorde).
- **Un échec n'était pas un défaut** : les trois analyses Windows « non ouvertes »
  existent, mais la collecte publie ses analyses **fusionnées par famille**
  (`Prefetch.csv`, `MFT et USN.csv`, `EVTX.csv`) ; le harnais cherchait les noms
  de sources. Rejeu après correction du harnais : quatre OK.

## Ce qui reste

- **Cosmétique, non corrigé** : la barre d'état est surchargée à gauche (le
  libellé de source est comprimé à quelques pixels, visible sur toutes les
  captures) — à reprendre dans une passe d'interface, avec captures ;
- le tableau du bilan reste vide pendant un import, alors que la collecte avance ;
- les chemins de plus de 260 caractères exigent `LongPathsEnabled=1` sur Windows :
  le produit s'appuie sur le système, aucun contournement n'est en place ;
- les messages techniques du cœur restent écrits en français (916 chaînes visibles
  sur 924 sont traduites ; le reste est dans les chemins d'erreur profonds) ;
- **la publication de la 0.4.2**, qui attend l'accord.

## Décisions à ne pas rouvrir

- L'interface est en **anglais seul** depuis la 0.3.2 ; cette passation reste en
  français, comme les constats de recette.
- **Aucun push sur `main` sans accord explicite** dans la session en cours.
- Les releases sont publiées **sous le compte du mainteneur**, jamais par le bot.
- Une collecte publie ses analyses **par famille** ; les analyses par fichier
  restent sur disque, ce n'est pas une perte.
- Les numéros : `0.x.0` pour un lot accumulé, `0.0.x` pour un correctif.

## Pièges connus, payés une fois

- **Jamais deux suites pytest en parallèle** : DuckDB prend un verrou et la
  seconde se fige sans message.
- **La porte est la seule autorité** : `pytest` lancé à la main sans
  `PYTHONUTF8=1` fait échouer un test sur un nom de fichier accentué, sur un
  arbre que la porte appelle vert.
- **Sur la VM, l'index de chronologie est lent** (I/O) : 20 minutes sur 38
  analyses là où la tour met des secondes. Ne pas conclure à un blocage.
- Les captures doivent être **zoomées** avant d'en tirer un défaut : un texte
  lu sur une vignette m'a fait enregistrer six boutons qui étaient des champs.
- `findstr` ne trouve pas un texte accentué (page de code de la console) :
  chercher avec un script Python.

## Première chose à faire à la reprise

Lire `docs/development/RELEASE-NOTES.md` (section 0.4.2), puis, si l'accord est
donné : `git checkout main`, `git merge --ff-only hermes/0.4.2`, `git push main`,
`git tag -a v0.4.2`, `git push origin v0.4.2`, et suivre le run de publication.
Vérifier ensuite que la release est bien sous le compte du mainteneur.
