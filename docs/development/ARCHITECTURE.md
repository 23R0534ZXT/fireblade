# Architecture de Fireblade

L’application utilise Python et trois dépendances directes : DuckDB, PySide6 Essentials et openpyxl. Le code est organisé sous `src/fireblade` et les imports nomment explicitement leur couche.

## Couches

| Dossier | Rôle | Dépendances principales |
|---|---|---|
| `core/` | Données, import, requêtes, filtres, règles, notes et export | Python, DuckDB, openpyxl pour XLSX |
| `ui/` | Fenêtre, dialogues, grille, menus et tâches Qt | Core, runtime, PySide6 |
| `runtime/` | Bootstrap, ressources intégrées et emplacements Windows | Bibliothèque standard ; chargement différé de l’interface |
| `validation/` | Parcours automatiques dans le programme Windows | UI, core et API Windows |

Le moteur reste importable sans Qt. Les modèles métier sont des dataclasses simples. Les menus et dialogues n’importent pas la classe Window ; leurs commandes sont raccordées par l’interface. Aucun conteneur d’injection, serveur ou système de plugins n’est nécessaire.

## Où modifier quoi

| Besoin | Fichier |
|---|---|
| Import, groupes, pagination, signets, transactions et export | `src/fireblade/core/engine.py` |
| Filtres, groupes logiques, vues et clés de tri | `src/fireblade/core/models.py` |
| Compilation SQL paramétrée et validation des règles | `src/fireblade/core/conditions.py` |
| Limites de ressources et lecture TOML | `src/fireblade/core/settings.py` |
| Bibliothèque globale, correspondance par noms et persistance | `src/fireblade/core/rule_store.py` |
| Lecture/écriture XLSX progressive | `src/fireblade/core/spreadsheets.py` |
| Signatures et dispositions forensic | `src/fireblade/core/profiles.py` |
| Annulation indépendante de Qt | `src/fireblade/core/errors.py` |
| Fenêtre et coordination des commandes | `src/fireblade/ui/app.py` |
| Modèle Qt paginé et rendu de la grille | `src/fireblade/ui/grid.py` |
| Dialogues d’import et éditeurs | `src/fireblade/ui/dialogs.py`, `advanced_dialogs.py` |
| Menus contextuels et geste de groupement | `src/fireblade/ui/menus.py`, `grouping.py` |
| Onglets et sessions | `src/fireblade/ui/workspace.py` |
| Commandes des règles globales | `src/fireblade/ui/shared_rules.py` |
| Palette et tâches en arrière-plan | `src/fireblade/ui/theme.py`, `workers.py` |
| Guide, licences et informations du build | `src/fireblade/ui/help_dialogs.py` |
| Diagnostic avant le chargement des DLL | `src/fireblade/runtime/bootstrap.py` |
| Emplacements utilisateur et ressources intégrées | `src/fireblade/runtime/windows_paths.py`, `resources.py` |
| Contrôles dans le véritable programme Windows | `src/fireblade/validation/windows_check.py` |
| Construction et contrôle du fichier unique | `scripts/windows/build.py`, `verify.py`, `bundle.py` |
| Paramètres intégrés au programme | `config/fireblade.toml` |

## Utiliser le moteur seul

Depuis l’environnement installé en mode éditable :

```python
from fireblade.core.engine import Case
from fireblade.core.models import Filter, View
from fireblade.core.settings import Settings

case = Case("enquete.timeline", settings=Settings(memory_mb=256, threads=1))
try:
    if not case.headers:
        case.import_csv("artefacts.csv")
    column = case.headers.index("User")
    view = View(filters=[Filter(column, "contains", "alice")], groups=[column])
    print(case.page(view))
finally:
    case.close()
```

Ne jamais interpoler une valeur utilisateur dans SQL : les identifiants de colonnes sont générés et les valeurs sont liées avec `?`. Un nouvel opérateur demande une déclaration dans `models.py`, sa compilation dans `conditions.py` et un test de comportement du moteur.

## Données et compatibilité

Les valeurs source sont stockées en VARCHAR. Le numéro interne suit l’ordre des enregistrements importés. Les comparaisons numériques utilisent une conversion exacte avec chemin rapide HUGEINT pour les chaînes entières et repli DECIMAL ; elles ne passent pas par un flottant.

Les tables de données, métadonnées, signets et vues vivent dans la base `.timeline`. Les vues JSON acceptent les nouveaux champs avec une valeur par défaut. Une modification du schéma des tables demanderait une migration explicite ; la réorganisation du package Python n’en impose pas.

Les sessions JSON conservent des références, des vues et un état d’en-tête. Leurs règles globales restent dans le profil utilisateur et ne sont pas copiées dans les vues locales.

## Concurrence et annulation

Chaque Case possède une connexion DuckDB et un verrou sérialisant ses opérations. Les accès coûteux passent dans les jobs Qt, hors du fil de l’interface. Un ContextVar conserve la demande d’annulation du job jusqu’à l’entrée dans le moteur. Une annulation attendue possède son propre signal, distinct d’une erreur.

Le COMMIT et le ROLLBACK engagés sont protégés contre une nouvelle interruption native. L’annulation est vérifiée avant validation. Une demande trop tardive n’annule pas rétroactivement une transaction terminée.

Avant un nouvel import, Window mémorise seulement le chemin de l’ancienne analyse, son identité de source, sa vue et son état d’en-tête. Après échec, l’importeur est fermé avant réouverture de l’ancienne base. Les buffers ne sont pas dupliqués dans le snapshot.

## Mémoire

- La grille charge des pages ; chaque parent possède une fenêtre bornée de lignes ou groupes.
- Replier un groupe libère ses descendants et leurs annotations.
- Les notes résident dans les nœuds chargés ; `GridModel.notes` expose seulement ce cache de pages.
- Un onglet inactif ne garde ni connexion DuckDB ni modèle Qt.
- Les couleurs sont évaluées sur une petite relation VALUES paramétrée, alimentée par les seules colonnes nécessaires des lignes déjà chargées. La table complète n’est pas relue pour colorer une page.
- Les règles locales et globales restent séparées, avec priorité locale : au maximum 32 de chaque type.
- Un cache temporaire de tri contient des couples position/identifiant. Il évite de refaire le tri pour les pages profondes et disparaît à la fermeture.
- Les callbacks des jobs terminés sont déconnectés pour libérer leurs références.

Le buffer DuckDB n’est pas un plafond global de RAM. Les cellules larges et les multiples branches ouvertes gardent un coût variable.

## Annotations et exports

`bookmark_many` traite une sélection explicite en transaction. Marquer préserve une note existante, ajouter concatène, remplacer écrase explicitement et retirer supprime le signet. La révision du cache de tri des signets change après validation seulement.

`export(..., include_annotations=True)` ajoute le numéro d’enregistrement, le signet et la note. Les champs d’origine ne sont pas renommés ; les noms générés sont suffixés en cas de collision. Les écritures passent par un temporaire puis un remplacement atomique.

## Fichier Windows unique

Le bootstrap charge d’abord les fonctions de diagnostic de la bibliothèque standard, puis l’interface. PyInstaller embarque le runtime, les DLL, la configuration par défaut, le guide, les notices et les métadonnées dans `Fireblade.exe`.

`runtime/resources.py` résout les fichiers en lecture seule depuis le dépôt pour les sources, ou depuis le dossier temporaire d’extraction pour le programme figé. Les données utilisateur ne sont jamais écrites dans les ressources intégrées.

La configuration explicite et celle du profil ont priorité sur le défaut embarqué. Une ancienne configuration à côté de l’exécutable reste facultativement lisible. L’absence de fichier adjacent est testée.

`scripts/windows/verify.py` ne copie que le `.exe` dans un dossier vide. Il retire les chemins du Python hôte, isole TEMP/LOCALAPPDATA, lance les contrôles et vérifie le nettoyage. La construction ne publie le binaire dans `dist/` qu’après succès.

La publication GitHub ne s’exécute qu’après succès sur main. Les rapports sont des artefacts de développement séparés ; le seul fichier joint à la préversion est le programme.
