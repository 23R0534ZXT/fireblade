# Qualification visuelle et CSV 3 GiB

Cette suite complète les tests unitaires et les treize contrôles rapides du fichier autonome. Elle vise les problèmes de rendu et les opérations longues qui ne sont pas démontrés par quelques enregistrements de test. Une Release ne peut être publiée que si cette suite réussit aussi.

## Ce qui est exécuté

Le job Windows télécharge le véritable Fireblade.exe construit dans la même exécution. Le programme est copié seul dans un autre dossier et lancé sans chemins du Python hôte. Les interactions utilisent QtTest pour les clics et frappes, et un QContextMenuEvent pour ouvrir les menus d’en-têtes. Ce sont des parcours automatisés de l’interface réelle, pas des tests humains physiques.

### Rendu

`scripts/windows/visual_matrix.py` lance le .exe avec les préférences Windows clair et sombre et QT_SCALE_FACTOR 1, 1.25, 1.5 et 2. Les réglages du profil de test sont restaurés ensuite.

Les captures couvrent accueil, menus, boutons, grille, recherche, éditeurs et fenêtre inactive. Le programme mesure les pixels sombres des glyphes et leur contraste avec le fond. Un test de régression confirme qu’un bouton volontairement blanc sur fond clair est refusé. Les rôles de palette seuls ne constituent pas une preuve du rendu.

### Fichier volumineux

`scripts/windows/dataset.py` écrit séquentiellement un fichier réel d’au moins 3 × 1024³ octets. Il ne crée pas un fichier creux et ne répète pas seulement un petit bloc. Les colonnes comprennent dates, artefacts, utilisateurs, machines, grands identifiants, chemins, tailles, hachages et contenus pseudo-aléatoires uniques, commandes, JSON, Unicode, cellules vides, guillemets et champs multilignes.

Une graine fixe rend la génération reproductible. Pendant la génération, Python calcule indépendamment des comptages de référence. La taille, le nombre d’enregistrements, le SHA-256 et le temps de génération sont conservés. Les données sont synthétiques ; le cache du système de fichiers n’est pas purgé.

### Parcours dans le programme

- Import intégral en lecture seule ; nombre d’enregistrements, empreinte et valeurs originales vérifiés.
- Douze configurations de regroupement, dont trois niveaux, champs vides et identifiants de forte cardinalité ; vérification des comptages et pages avec l’oracle Python.
- Regroupements sous filtre actif et quarante cycles de dépliage/repliage sur trois niveaux, avec suivi mémoire.
- Recherche au clavier, éditeur OU, filtres exacts, combinés, regex RE2, NULL et dates ; erreur de regex suivie d’une reprise.
- Tris de grands entiers et de dates dans les deux sens ; tri multi-colonnes, pages profondes, cache et retour arrière.
- Règles globales/locales, sélection à la souris, marquage, ajout, remplacement et retrait des notes, résultats vides et reprise.
- Vues nommées, colonnes, changement d’onglet, libération et réouverture de la base, session et persistance des notes.
- CSV et XLSX filtrés avec annotations, comptages exportés et export CSV complet de plusieurs Go. Le CSV complet est relu indépendamment et son SHA-256 comparé à la source du générateur.
- Annulation après le début d’écriture d’un export, préservation de la destination et nettoyage du temporaire.
- Annulation d’un second import 3 GiB après l’écriture effective d’au moins un lot, vérification du rollback sans tables partielles et de la restauration de l’analyse précédente.
- Empreinte finale de la source et réutilisation de la base.

## Mesures

Chaque étape enregistre sa durée. Le processus Windows mesure son working set et son pic avec l’API système ; un timer de l’interface relève ses intervalles pour signaler les longues pauses. Les versions, système, CPU logique, police et style sont enregistrés. La croissance du working set après échauffement des cycles est contrôlée ; un seuil QA de 1536 MiB repère un emballement, sans constituer un plafond de RAM garanti par le produit.

Le premier passage de cette qualification a trouvé un dépassement mémoire réel à l’import du fichier de 3 222 648 632 octets. Le moteur traite désormais les gros CSV par fichiers temporaires bornés à 16 MiB (moins avec un budget réduit), séparés sur les limites d’enregistrements CSV complets. Chaque lot est inséré par DuckDB dans la même transaction ; l’annulation retire tous les lots. Les champs multilignes, séparateurs, encodages, doublons d’en-têtes et grands identifiants sont vérifiés. Les exports utilisent un seul espace de tri pour tenir dans le budget mémoire.

Les rapports JSON et PNG sont publiés dans Actions. Les CSV et bases volumineuses ne sont pas joints aux artefacts. Le générateur et la graine permettent de reconstruire les données.

## Reproduire sur Windows

```powershell
python -m scripts.windows.visual_matrix --exe dist/Fireblade.exe --out artifacts/visual
python -m scripts.windows.qualify generate --directory C:\Temp\fireblade-data --out artifacts/large-data --gib 3
python -m scripts.windows.qualify run --directory C:\Temp\fireblade-data --out artifacts/large-data --exe dist/Fireblade.exe
```

Utiliser un dossier de données nouveau et au moins 12 GiB libres avant génération. Les sorties sont destinées aux développeurs ; l’utilisateur final conserve uniquement le .exe.

## Limites

Les runners GitHub ne remplacent pas un poste utilisateur Windows 10/11 ni les données réelles d’une enquête. Les partages UNC, politiques de parc, gestes physiques de l’Explorateur, toutes les variantes de CSV, pannes brutales et sessions de plusieurs jours restent hors de cette qualification. « Tout testé » serait une affirmation excessive ; les rapports détaillent ce qui a effectivement été exercé.
