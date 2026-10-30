# Développer et contribuer

## Installer

Depuis la racine du dépôt sur Windows, avec Python 3.12 64 bits :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements/development.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m fireblade
```

Les dépendances d’exécution épinglées vivent dans `requirements/runtime.txt`. Les outils de test et de construction sont séparés. Le layout `src/` évite d’importer accidentellement un module resté à la racine.

`scripts/windows/Lancer.cmd` prépare aussi un environnement de sources. Les lanceurs sont destinés au développement ; les utilisateurs du programme n’ont besoin que du `.exe`.

## Tester

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest tests/core -q
.\.venv\Scripts\python.exe -m pytest tests/ui -q
```

Les fixtures gardent une seule QApplication par processus et isolent le stockage utilisateur. Les tests Windows restent réservés à la sémantique native des verrous et fichiers Windows.

Un changement de requête, d’import, d’annulation ou de persistance doit être vérifié sur son comportement observable, notamment en cas d’échec. Garder les tests lisibles et les jeux de données synthétiques.

## Construire

```powershell
py -3.12 -m scripts.windows.build
```

La commande crée un environnement de construction isolé et produit `dist/Fireblade.exe` après les contrôles natifs. `scripts/windows/bundle.py` collecte les licences et versions depuis cet environnement. Les ressources source sont dans `config/`, `docs/guides/`, `licenses/` et `LICENSE`.

Pour expérimenter avec une autre version ou construction de Qt/DuckDB, modifier les dépendances de construction et reconstruire le programme. Les sources du projet et les points d’entrée de PyInstaller restent disponibles ; aucun composant propriétaire du projet n’est nécessaire à cette reconstruction.

Ne pas committer les environnements, données d’analyse, DLL, fichiers temporaires ou sorties de construction. Les rapports CI sont des artefacts d’Actions, pas des fichiers de la racine.

## Mesurer

Les scripts dans `scripts/benchmarks` restent séparés du programme :

```powershell
.\.venv\Scripts\python.exe -m scripts.benchmarks.benchmark --directory C:\Temp\fireblade-bench --gib 1.05
.\.venv\Scripts\python.exe -m scripts.benchmarks.benchmark_sort --help
.\.venv\Scripts\python.exe -m scripts.benchmarks.benchmark_ui --help
.\.venv\Scripts\python.exe -m scripts.benchmarks.verify_import_cancel --help
```

Utiliser un nouveau dossier pour les données générées. Indiquer le système, les versions, le matériel, les données et le périmètre exact mesuré. Les anciens résultats dans `docs/archive` ne servent pas de garantie de performances Windows.

## Proposer un changement

- Lire l’architecture et modifier la couche concernée.
- Conserver les valeurs source et les paramètres SQL liés.
- Garder les opérations volumineuses hors du fil de l’interface.
- Respecter la pagination et libérer les pages obsolètes.
- Préserver les anciennes analyses et vues par défaut compatibles.
- Décrire le problème concret, le comportement obtenu et les vérifications utiles dans la PR.

Le workflow valide la PR, puis main après intégration. Seul main publie une préversion avec le fichier autonome. Le statut de prototype reste explicite.
