# Validation des versions 0.1 à 0.4

Environnement : Linux x86-64, Python 3.12.14, DuckDB 1.5.6, Qt/PySide6 Essentials 6.12.0. Tests UI exécutés via `QT_QPA_PLATFORM=offscreen`. Pas de test sous Windows ou macOS, pas de binaire Windows livré.

## Benchmark du moteur

Ces mesures ont été réalisées sur la version 0.1 ; elles sont conservées comme référence, sans revendiquer une nouvelle mesure d’import après le découpage du code en version 0.2.

CSV synthétique de **1 129 468 693 octets** (~1,13 Go / 1,05 Gio), **2 890 000 lignes**, six colonnes. Deux threads DuckDB ; limite de buffer 256 MB ; mesure de RSS du processus par psutil toutes les 50 ms. La génération du CSV est exclue des temps. Le processus mesuré ne charge pas Qt.

| Opération | Temps |
|---|---:|
| Import, deux passes SHA-256 incluses | 10,403 s |
| Première page, ordre source | 0,006 s |
| Premier niveau d’une vue regroupée sur deux colonnes | 0,012 s |
| Première page triée numériquement (DECIMAL exact) | 11,573 s |
| Comptage avec filtre sur EventID | 0,005 s |

Pic RSS observé : **375,8 Mio**. La limite de buffer DuckDB n’est donc pas une limite globale du processus. Base finale : 37 498 880 octets.

Les blocs CSV sont très répétitifs et favorisent fortement la compression. Le système de fichiers était en cache après la génération, et la machine cloud / son stockage ne sont pas représentatifs d’un poste d’enquête Windows. La mesure ne couvre ni la grille Qt, ni un export volumineux, ni un fichier réel d’artefacts Windows, ni un tri profond, ni un nombre extrême de groupes. Il n’y a eu aucune comparaison instrumentée avec Timeline Explorer. Ces chiffres vérifient le fonctionnement au-delà de 1 Go dans ce scénario seulement.

Le tri numérique exact est ici le point lent : il utilise DECIMAL(38,10) pour préserver les grands entiers plutôt que de les arrondir en flottants. Ce coût est explicite ; il reste à profiler et optimiser sur des données réelles. Le résultat brut et les versions sont conservés dans `benchmark-results.json` ; le script de reproduction est `scripts/benchmark.py`.

## Vérifications fonctionnelles

`python -m pytest -q` couvre l’import fidèle des valeurs non vides, zéros initiaux et grands entiers, les champs multilignes / Unicode, UTF-16 et Latin-1, les filtres combinés et dates, regex invalides, tentatives d’injection comme valeurs littérales, groupes imbriqués avec NULL, pagination et fenêtre mémoire, signets et vues après réouverture, export des résultats et des groupes, erreurs CSV avec rollback, modification de la source pendant l’import, annulation et chargement asynchrone de la grille.

La capture `preview.png` utilise un petit CSV de démonstration synthétique et présente une vue regroupée ; elle ne correspond pas aux données du benchmark.

## Ressources et modularité, version 0.2

La version 0.2 conserve uniquement DuckDB et PySide6 Essentials comme dépendances d’exécution. Les paramètres de ressources, données de vues, workers, grille et thème sont isolés dans leurs modules ; le moteur reste utilisable sans Qt. La limite de buffer par défaut passe de 512 à 256 MB, sans prétendre limiter toute la mémoire du processus.

Une mesure supplémentaire ouvre la base synthétique précédente de 2 890 000 lignes dans Qt sans écran, regroupe une colonne puis déplie et replie le premier groupe huit fois. Pic RSS observé du processus complet, Qt inclus : **138,9 Mio**. Après chaque repli, le modèle ne conserve plus les lignes du groupe. Il s’agit d’une ouverture de base déjà importée, pas d’un import ; cette mesure n’est donc pas comparable au pic de 375,8 Mio du benchmark moteur.

Résultat brut : `ui-resource-results.json`. Reproduction après création de la base avec `scripts.benchmark` :

```sh
.venv/bin/python -m scripts.benchmark_ui --case /tmp/timeline-bench-new/benchmark.timeline --output /tmp/ui-resources.json
```

Un second passage de **100 cycles** a atteint un pic de **140,0 Mio** et terminé à **138,8 Mio**, après une montée progressive des allocations / caches. Les données sont dans `ui-resource-100.json`. Cette vérification cherche une accumulation évidente sur ce scénario court ; elle ne démontre pas l’absence de fuite mémoire dans toutes les utilisations. Reproduction : ajouter `--cycles 100` à la commande précédente.

Les tests vérifient aussi les paramètres personnalisés et invalides, l’éviction des pages de groupes, le repli avec libération des descendants et l’annulation de jobs devenus obsolètes avant leur exécution. Les branches laissées ouvertes et les notes restent un coût mémoire variable. Les mesures ne remplacent pas des essais sur Windows avec des exports réels.

## Interface classique, version 0.3

Palette claire, contrôles standard, menus de bureau, grille plus compacte et écran d’ouverture simple. Les options de tri et les actions secondaires passent dans les menus. Aucune dépendance d’exécution supplémentaire. Le moteur et ses réglages restent identiques à la version 0.2. Les 23 tests existants passent après ce changement ; les deux captures ont été régénérées et inspectées sous Linux sans écran. Les chiffres de ressources ci-dessus proviennent des versions précédentes et n’ont pas été remesurés pour cette modification visuelle.

## Parcours de bureau, version 0.4

**30 tests passent sous Linux**, Python 3.12.14, avec Qt sans écran. Les nouveaux cas couvrent : import réel déclenché par événements Qt de glisser-déposer, source et destination accentuées, vérification du hash de source inchangé, réouverture d’analyse et signets, actions contextuelles de tri texte / nombre et regroupements à plusieurs niveaux, filtre prérempli depuis un en-tête, masquage de colonne, copie et filtres de cellules (y compris NULL), destination d’import protégée contre l’écrasement et analyse courante conservée si une autre base est invalide ou absente.

L’import regroupe désormais la destination et les options CSV dans une seule fenêtre. Déposer un fichier et passer un chemin à la ligne de commande réutilisent les mêmes commandes que les menus. Les dialogues et menus contextuels sont isolés dans des modules simples, sans nouvelle dépendance d’exécution. Le filtre « Différent de » utilise une comparaison incluant les NULL pour que l’exclusion d’une valeur ne supprime pas les cellules vides.

Un workflow Windows est fourni pour les tests sous Python 3.11 / 3.12 / 3.13 et la construction portable après succès. Son YAML a été lu et sa structure vérifiée localement ; **aucun job Windows ou build Windows n’a été exécuté dans cet environnement**. Le contrôle portable prévu est un lancement `--help`, pas un test complet de l’interface empaquetée. Les statistiques mémoire des versions antérieures restent des références historiques et ne sont pas de nouvelles mesures de cette version.

## Suite du prototype : tris et interruption

Ce point de travail comptait 48 tests sous Linux après optimisation de la conversion entière, ajout d’un cache unique pour les pages triées profondes et distinction entre annulation et erreur dans les jobs Qt. Les notes `PROTOTYPE.md` donnent le périmètre, les tests d’interruption et les limites. Une nouvelle comparaison du moteur sur la même base synthétique de 2,89 millions de lignes est conservée dans `sort-prototype-results.json`, avec vérification des valeurs renvoyées à chaque décalage. Cette mesure ne couvre pas l’interface Windows.

## Reprise d’import

**62 tests passent sous Linux** après ajout de la restauration de l’analyse précédente, de la protection des validations / retours en arrière et du contrôle de détection ambiguë d’en-tête. Le nouveau fichier `tests/test_import_transactions.py` couvre les limites de transaction, l’interruption native de la lecture CSV et la reprise de la même connexion. Les tests de bureau vérifient la restauration réelle des filtres, regroupements, tri, notes, colonnes et l’import suivant, ainsi que le cas où l’ancienne analyse a été supprimée ou remplacée, y compris par le même CSV décodé avec un autre encodage.

Un essai séparé sur le CSV synthétique de 1,13 Go interrompt le traitement à 26,92 % de progression native, constate un retour en arrière sans table partielle et réutilise la base. Le hash de source est inchangé. Voir `import-cancel-prototype-results.json` et `PROTOTYPE.md`. Les vérifications restent locales sous Linux ; aucun build ni essai Windows n’a été exécuté.
