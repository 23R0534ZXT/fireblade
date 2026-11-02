# Audit approfondi Fireblade — 2 novembre 2026

Version examinée : `782600867e72a340ca54b6f80e1377f2ff89b363` (0.4.0).
Linux x86-64, Python 3.12.14, DuckDB 1.5.6, PySide6 6.12.0, interface Qt
`offscreen`. Environnement limité à 8 Gio de RAM et deux cœurs CPU par quota.
Les résultats ci-dessous décrivent l'état avant correction. Le correctif appliqué
ensuite est décrit dans la section « Correctif SESSION-01 ».

## Résultat

**Un défaut confirmé de sauvegarde de session, reproduit par deux dépassements
de limites.** La suite existante ne le détecte pas : 901 tests réussis,
28 ignorés, aucun échec, en 129,245 secondes.

Les 42 scénarios complémentaires CSV passent. Les tests de charge, d'annulation,
de pagination profonde et de comparaison indépendante des résultats passent.
Les résultats structurés et les motifs des tests ignorés figurent dans
[le rapport JSON](20261102-adversarial-audit-linux.json).

## SESSION-01 — Une sauvegarde annoncée comme réussie peut être impossible à rouvrir

Priorité proposée : **P2**, perte d'accès à l'espace de travail sauvegardé.

`write_session()` dans `src/fireblade/core/sessions.py:11` écrit le JSON puis
remplace le fichier précédent sans contrôler les limites que `read_session()`
applique : 1 à 1000 analyses et 4 194 304 octets maximum.
`WorkspaceMixin.save_session()` dans `src/fireblade/ui/workspace.py:103`
appelle cet écrivain sans ces contrôles et annonce ensuite la réussite.

Deux reproductions avec des bases `.timeline` synthétiques valides :

| Scénario | Sauvegarde | Réouverture |
|---|---|---|
| 1000 analyses, vues simples | Réussie | Réussie |
| 1001 analyses | Réussie ; remplace la session valide précédente | Refus : « Une session doit contenir de 1 à 1000 analyses » |
| 320 analyses avec une recherche de 14 000 caractères par vue | Réussie ; fichier de plus de 4 Mio, remplace la session précédente | Refus : « Session limitée à 4 Mo » |

La seconde limite est également reproduite par la méthode réelle de sauvegarde
de l'interface, sur 320 références à une base synthétique valide. Résultat :
aucune erreur de sauvegarde, message **« Session enregistrée : onglets, vues et
dispositions des colonnes »**, fichier de 4 972 777 octets, puis refus de
réouverture **« Session limitée à 4 Mo »**. Les documents et recherches ont été
construits par programmation, sans saisir manuellement 320 recherches.

Les bases et leurs annotations ne sont pas supprimées par ce défaut. En revanche,
la session précédente est remplacée : ses onglets, filtres et dispositions ne
peuvent plus être restaurés normalement depuis ce fichier. Les sauvegardes
internes des cases via `InvestigationLibrary.save()` ont des contrôles séparés ;
ce résultat concerne la sauvegarde de session autonome et ses appels directs.

Reproduction depuis la racine du dépôt, en choisissant un dossier neuf :

```bash
.venv/bin/python -m scripts.benchmarks.audit_session_limits \
  --directory /tmp/fireblade-audit-sessions
```

Sous la version auditée, la commande retourne **1** et produit `results.json`
avec un contrôle réussi et deux contrôles échoués. Elle utilise exclusivement
des données synthétiques et refuse un dossier déjà existant.

Correction recommandée : valider le nombre d'analyses et la taille UTF-8 du
fichier temporaire **avant** `os.replace()`, et conserver la précédente session
si la nouvelle dépasse une limite. Ajouter les deux cas de reproduction aux
tests de sauvegarde et vérifier la remontée de l'erreur dans l'interface.

## Contrôles complémentaires réussis

- **CSV : 42 scénarios.** Combinaisons de virgule, point-virgule, tabulation et
  barre verticale ; UTF-8, UTF-8 avec BOM, UTF-16 et UTF-16 BE ; import direct
  et import forcé par petits lots. Comparaison indépendante avec `csv.reader`,
  recherche, filtres, groupes, export, signets, vues et réouverture. Cellules
  vides, `NULL` textuel, grands identifiants, zéros initiaux, Unicode, guillemets,
  lignes multiples, caractères NUL, espaces et contenus ressemblant à du SQL.
- **Annulation réelle depuis un autre thread pendant l'import de 1,05 Gio.**
  Annulation normalisée en `OperationCancelled`, aucune table partielle,
  fichiers temporaires nettoyés, empreinte source inchangée, réutilisation de la
  même base pour un nouvel import réussie. Le temps enregistré de 0,732 seconde
  inclut aussi le réimport et la vérification SHA-256 après l'interruption ;
  il ne représente pas une mesure isolée de latence d'annulation.
- **Pagination triée avec 64 Mo de budget DuckDB sur 2 890 000 lignes.**
  Pages aux positions 1000, 1 445 000, 2 889 750 et au-delà de la fin ; signets
  et filtres OU. Résultats comparés à un calcul Python utilisant la structure
  connue des données, sans reproduire la requête SQL du logiciel.
- **Grand jeu : 8 380 000 lignes.** Réouverture, premières pages, pages centrales
  et finales, tri numérique profond, comptes de groupes et filtres comparés à
  un oracle Python. Export de 104 750 lignes : chaque valeur et l'ordre vérifiés.
  Empreinte SHA-256 de la source vérifiée après les opérations.

## Mesures de charge

| Mesure | Jeu de 1,05 Gio | Jeu de 3,05 Gio |
|---|---:|---:|
| Taille CSV exacte | 1 129 468 693 octets | 3 275 068 297 octets |
| Enregistrements | 2 890 000 | 8 380 000 |
| Import avec deux passes SHA-256 | 33,810 s | 100,947 s |
| Première page | 0,007 s | 0,008 s |
| Premier niveau de groupement | 0,005 s | 0,013 s |
| Première page triée numériquement | 0,216 s | 0,487 s |
| Compte filtré | 0,004 s | 0,009 s |
| Pic RSS échantillonné pendant le benchmark | 259,5 Mio | 324,2 Mio |

Les deux benchmarks utilisent un budget DuckDB de 256 Mo et deux threads.
Les données sont synthétiques, répétitives et fortement compressibles : ces
mesures ne prédisent pas les performances d'une collecte arbitraire. Certains
contrôles tournaient simultanément et le cache disque peut être chaud. Le budget
DuckDB ne limite pas toute la mémoire du processus.

Commandes de charge utilisées, avec des dossiers neufs :

```bash
.venv/bin/python -m pytest -q --junitxml=/tmp/fireblade-pytest.xml
.venv/bin/python -m scripts.benchmarks.benchmark --directory /tmp/fireblade-1gib --gib 1.05
.venv/bin/python -m scripts.benchmarks.benchmark --directory /tmp/fireblade-3gib --gib 3.05
```

## Limites de cet audit

Les 28 tests ignorés concernent principalement les hôtes et lecteurs .NET réels,
Shellbags natif, la sémantique Windows des fichiers et chemins UNC, un encodeur
GIF absent et un jeu externe de 3 Gio non présent à l'emplacement attendu. Le
grand jeu synthétique créé ici est distinct de ce jeu externe.

La suite inclut des parcours d'interface et 320 bases réelles ; l'exécution Qt
reste hors écran sous Linux. Aucun EXE Windows, bureau Windows interactif,
partage SMB réel, panne électrique ou qualification de tous les moteurs Windows
embarqués n'a été testé ici. Les résultats de ce rapport ne garantissent pas
l'absence d'autres bugs et ne remplacent pas la qualification Windows native.

## Correctif SESSION-01

Le correctif contrôle le nombre d'analyses et l'onglet actif avant toute écriture,
puis la taille réelle en octets du fichier temporaire UTF-8 avant de remplacer
la session existante. Les limites de lecture et d'écriture utilisent désormais
les mêmes constantes. Un dépassement conserve le fichier précédent et nettoie
le fichier temporaire ; l'interface reçoit l'erreur sans annoncer de réussite.

Les tests ajoutés couvrent la conservation de la session précédente, le refus
d'une nouvelle session trop grande, les caractères UTF-8 multioctets, la limite
exacte en octets, 1000 analyses distinctes, les indices d'onglet invalides et la
remontée de l'erreur dans l'interface. Les 36 tests ciblés passent. L'outil
`scripts.benchmarks.audit_session_limits` passe ses trois contrôles après correction.

La suite complète après correction passe également : **912 tests réussis,
28 ignorés, aucun échec**, en 129,81 secondes sous Linux avec Qt hors écran.

Après intégration des nouveautés de `main` jusqu'à `c35b68f` (navigation des
analyses, marquage des lignes, rapports de collecte et contexte EVTX), la suite
complète passe : **922 tests réussis, 28 ignorés, aucun échec**, en 150,81 secondes.
Les trois contrôles de l'outil d'audit des sessions passent également sur cet ensemble.
