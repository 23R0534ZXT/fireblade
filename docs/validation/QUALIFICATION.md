# Qualification visuelle et CSV 3 GiB

Cette suite complète les tests unitaires et les treize contrôles rapides du fichier autonome. Elle vise les problèmes de rendu et les opérations longues qui ne sont pas démontrés par quelques enregistrements de test. Une Release du programme ne peut être publiée que si cette suite réussit aussi.

## Ce qui est exécuté

Le job Windows télécharge le véritable Fireblade.exe construit dans la même exécution. Le programme est copié seul dans un autre dossier et lancé sans chemins du Python hôte. Les interactions utilisent QtTest pour les clics et frappes, et un QContextMenuEvent pour ouvrir les menus d’en-têtes. Ce sont des parcours automatisés de l’interface réelle, pas des tests humains physiques.

### Rendu

`scripts/windows/visual_matrix.py` lance le .exe avec les préférences Windows clair et sombre et QT_SCALE_FACTOR 1, 1.25, 1.5 et 2. Les réglages du profil de test sont restaurés ensuite.

Les captures couvrent accueil, menus, boutons, grille, recherche, éditeurs et fenêtre inactive. Le programme mesure les pixels sombres des glyphes et leur contraste avec le fond. Un test de régression confirme qu’un bouton volontairement blanc sur fond clair est refusé. Les rôles de palette seuls ne constituent pas une preuve du rendu.

### Fichier volumineux

Les tests réutilisent le **CSV déjà publié**, sans le régénérer : **3 222 648 632 octets, 2 441 216 enregistrements**, SHA-256 `2382777d3917a973a1e5104b3bc404d02d3901aeff8104d34fc30e4264776cf0`.

`scripts/windows/existing_dataset.py` vérifie le fichier présent dans le dossier de données. À défaut, il récupère le ZIP de la [Release des données](https://github.com/23R0534ZXT/fireblade/releases/tag/test-data-3gib), vérifie son empreinte puis extrait le même CSV et vérifie son empreinte. Un fichier présent mais différent est refusé sans être remplacé. GitHub Actions met ce CSV en cache avec une clé contenant son SHA-256 ; chaque utilisation vérifie quand même son contenu.

Le [manifeste](datasets/3gib.json) identifie le téléchargement et le [référentiel des résultats](datasets/3gib-reference.json) conserve les comptages, sommes et échantillons indépendants calculés lors de sa création initiale. Les données restent synthétiques ; le cache disque n’est pas purgé. Le générateur historique reste disponible pour créer explicitement un autre jeu de données, mais les parcours de qualification et de diagnostic ne l’appellent plus.

Pour tester manuellement le CSV publié, voir [les étapes et résultats attendus](../guides/TESTER-3GIB.md).

### Parcours dans le programme

- Import intégral en lecture seule ; nombre d’enregistrements, empreinte et valeurs originales vérifiés.
- Douze configurations de regroupement, dont trois niveaux, champs vides et identifiants de forte cardinalité ; vérification des comptages et pages avec l’oracle Python.
- Regroupements sous filtre actif et quarante cycles de dépliage/repliage sur trois niveaux, avec suivi mémoire.
- Recherche au clavier, éditeur OU, filtres exacts, combinés, regex RE2, NULL et dates ; erreur de regex suivie d’une reprise.
- Tris de grands entiers et de dates dans les deux sens ; tri multi-colonnes, pages profondes, cache et retour arrière.
- Règles globales/locales, sélection à la souris, marquage, ajout, remplacement et retrait des notes, résultats vides et reprise.
- Vues nommées, colonnes, changement d’onglet, libération et réouverture de la base, session et persistance des notes.
- CSV et XLSX filtrés avec annotations, comptages exportés et export CSV complet de plusieurs Go. Le CSV complet est relu indépendamment et son SHA-256 comparé au CSV de référence publié.
- Annulation après le début d’écriture d’un export, préservation de la destination et nettoyage du temporaire.
- Annulation d’un second import 3 GiB après l’écriture effective d’au moins un lot, vérification du rollback sans tables partielles et de la restauration de l’analyse précédente.
- Empreinte finale de la source et réutilisation de la base.

## Mesures

Chaque étape enregistre sa durée. Le processus Windows mesure son working set et son pic avec l’API système ; un timer de l’interface relève ses intervalles pour signaler les longues pauses. Les versions, système, CPU logique, police et style sont enregistrés. La croissance du working set après échauffement des cycles est contrôlée ; un seuil QA de 1536 MiB repère un emballement, sans constituer un plafond de RAM garanti par le produit.

Le premier passage de cette qualification a trouvé un dépassement mémoire réel à l’import du fichier de 3 222 648 632 octets. Le moteur traite désormais les gros CSV par fichiers temporaires avec une cible de 16 MiB (moins avec un budget réduit), séparés sur les limites d’enregistrements CSV complets. Les octets sont comptés après chaque enregistrement ; le dernier enregistrement peut dépasser la cible et n’est jamais coupé. Chaque lot est inséré par DuckDB dans la même transaction ; l’annulation retire tous les lots. Les champs multilignes, séparateurs, encodages, doublons d’en-têtes et grands identifiants sont vérifiés. Les exports utilisent un seul espace de tri pour tenir dans le budget mémoire.

Le pilote traite les événements Qt puis cède explicitement l’interpréteur aux workers Python. Une attente QtTest longue conservait le GIL et faussait fortement les temps CSV/XLSX ; cette attente n’est plus utilisée pour patienter sur les opérations de fond.

Les rapports JSON et PNG sont publiés dans Actions. Les CSV et bases volumineuses ne sont pas joints aux artefacts de chaque exécution. Le CSV de référence dispose d’un téléchargement séparé dans la Release des données et est réutilisé entre les essais.

## Reproduire sur Windows

```powershell
python -m scripts.windows.visual_matrix --exe dist/Fireblade.exe --out artifacts/visual
python -m scripts.windows.qualify prepare --directory C:\Temp\fireblade-data --out artifacts/large-data --gib 3
python -m scripts.windows.qualify run --directory C:\Temp\fireblade-data --out artifacts/large-data --exe dist/Fireblade.exe
```

Réutiliser le même dossier de données et prévoir au moins 12 GiB libres pour la qualification. Si le CSV est absent, installer GitHub CLI (`gh`) et s’authentifier pour accéder à la Release privée, ou extraire manuellement le ZIP publié dans ce dossier. La commande `prepare` contrôle le SHA-256 ; elle ne crée pas de nouveau CSV. L’ancienne commande `generate` est conservée comme alias de `prepare` et ne régénère plus le fichier. Les sorties sont destinées aux développeurs ; l’utilisateur final conserve uniquement le .exe.

## Limites

Les runners GitHub ne remplacent pas un poste utilisateur Windows 10/11 ni les données réelles d’une enquête. Les partages UNC, politiques de parc, gestes physiques de l’Explorateur, toutes les variantes de CSV, pannes brutales et sessions de plusieurs jours restent hors de cette qualification. « Tout testé » serait une affirmation excessive ; les rapports détaillent ce qui a effectivement été exercé.


## Fonctions supplémentaires de la grille

Le contrôle embarqué `feature_checks.py` ajoute dix parcours : résumés et précision, navigation temporelle, épinglage, expressions/projections, recherche entre fichiers, cases booléennes/signets, réouverture, catalogue et lecteur XLS, session TLE, glyphes du thème sombre. Ils s’exécutent dans le véritable EXE avec les autres contrôles de fichier unique. Les nouveaux tests de sources couvrent aussi un vrai classeur BIFF XLS synthétique à deux feuilles, des erreurs de migration et les rejets de syntaxe.

Chaque variante Windows/DPI de la matrice vérifie désormais aussi le thème sombre propre à l’application et capture sa zone épinglée. Le contrôle des glyphes utilise le contraste effectif avec le fond, dans les deux thèmes.

Le référentiel du CSV existant contient les sommes de tailles par artefact et les comptes par journée calculés indépendamment lors de sa création. Le parcours intégré compare ces références avec les nouveaux résumés et groupes de dates, vérifie une projection CSV et recherche dans deux analyses dont la base multi-Go. Le catalogue d’en-têtes est une aide de présentation et ne remplace pas une qualification de tous les exports réels des outils référencés.
