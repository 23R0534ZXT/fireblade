# Fireblade 0.4.0 — comparaison mesurée avec Timeline Explorer

Ce document répond à une question simple : un analyste qui ouvre un gros CSV de journal,
que gagne-t-il avec Fireblade plutôt qu'avec Timeline Explorer ? Les deux outils ont été
mesurés sur **les mêmes fichiers**, sur **la même machine**, avec des méthodes comparables.

## Machine de mesure

- Intel Core i7-12700K (12 cœurs, 20 threads), 31,8 Go de RAM, Windows 11 (build 26200)
- Disque système avec 679 Go libres
- Fireblade 0.4.0 (branche `hermes/0.4.0`), Timeline Explorer 2026.10.0 + runtime .NET 10

## Les fichiers

Un faux journal `auth.log` exporté en CSV, huit colonnes (horodatage, hôte, utilisateur,
processus, EventID, source, message, chemin), généré de façon **reproductible** : chaque
taille a un contenu déterministe, ce qui permet de revérifier après coup que rien n'a été
perdu.

| Lignes | Taille |
| --- | --- |
| 250 000 | 28 Mo |
| 1 000 000 | 112 Mo |
| 4 000 000 | 453 Mo |
| 16 000 000 | 1,82 Go |
| 32 000 000 | 3,65 Go |

## Temps d'ouverture et mémoire

Fireblade mesuré avec le budget par défaut de 1 Go et quatre threads ; Timeline Explorer
mesuré tel qu'un analyste l'utilise, fenêtre affichée et CPU retombé.

| Fichier | Fireblade | TLE | Rapport temps | Fireblade (RAM) | TLE (RAM) |
| --- | --- | --- | --- | --- | --- |
| 28 Mo | **1,2 s** | 10,9 s | 8,9× plus rapide | ≤ 1,1 Go | 0,37 Go |
| 112 Mo | **5,1 s** | 9,8 s | 1,9× plus rapide | ≤ 1,1 Go | 0,78 Go |
| 453 Mo | 19,7 s | **17,1 s** | 1,2× plus rapide | ≤ 1,1 Go | 2,2 Go |
| 1,82 Go | 74,3 s | **51,8 s** | 1,4× plus rapide | ≤ 1,1 Go | 7,6 Go |
| 3,65 Go | 147,8 s | **108,3 s** | 1,4× plus rapide | 1,1 Go | **15,3 Go** |

Lecture honnête : **Timeline Explorer est plus rapide sur les gros fichiers** (1,4× à
3,65 Go), et Fireblade est plus rapide sur les petits (9× à 28 Mo, où le démarrage de
l'application .NET pèse lourd).

La différence décisive est ailleurs, dans la colonne mémoire : Timeline Explorer charge
le fichier entier en RAM et demande **environ 4,2 fois la taille du fichier** ; Fireblade
reste à **son budget**, quelle que soit la taille. À 3,65 Go, TLE occupe 15,3 Go ; Fireblade
plafonne à 1,1 Go (pic mesuré de l'extérieur, budget réglé à 1 Go ; le même import avec un
budget de 8 Go plafonne à 2,2 Go — la mémoire suit le réglage, pas le fichier).

## Ce que cela change sur une machine modeste

TLE lui-même documente sa limite : sur le fichier de 3,65 Go il affiche

> « The selected file is 3,653,736,773 in size and will take time to load.
> **TLE can handle files at least 14 GB in size**, but be patient… »

Cette phrase est cohérente avec la mesure : à 4,2× le fichier, 14 Go de fichier demandent
environ 59 Go de RAM, ce qui suppose une station de travail. Sur une VM de 8 Go, le plafond
pratique est un fichier d'environ **1,9 Go** ; au-delà, l'outil ne peut pas ouvrir le
fichier quel que soit le temps qu'on lui accorde.

Fireblade, sur la même VM de 8 Go, importe sans changer de comportement — c'est l'objet du
travail de cette version (commit par tranches au-delà de 2 Gio, budget qui grandit tout seul
jusqu'à la moitié de la RAM, voie bornée ligne par ligne en dernier recours).

## Ce que coûte l'intégrité

Fireblade calcule le SHA-256 du fichier **avant et après** l'import, pour qu'un fichier
modifié pendant la collecte ne passe pas inaperçu. Sur ce fichier de 3,65 Go, un passage
coûte **2,8 s** : environ 6 s sur les 148 s, soit 4 % du temps. Le reste est la lecture et
l'écriture des colonnes, pas la vérification.

## Le réglage d'effort ne change pas un seul fichier

Trois budgets sur le même fichier de 3,65 Go :

| Réglage | Temps | Débit |
| --- | --- | --- |
| 512 Mo, 1 thread | 143,7 s | 25,4 Mo/s |
| 1 Go, 4 threads (défaut) | 151,5 s | 24,1 Mo/s |
| 8 Go, 20 threads (maximum) | 146,6 s | 24,9 Mo/s |

C'est normal et c'est à documenter : **un seul fichier est une seule séquence de lecture**,
les threads n'y changent rien. Le réglage d'effort sert aux **dossiers** (beaucoup de
fichiers en parallèle) et au **budget mémoire** ; il ne rend pas un fichier unique plus
rapide. Là où il compte, mesuré sur 48 fichiers : 3,4 s à un thread, 1,2 s à quatre,
1,0 s à huit.

## Vérification : rien ne se perd

Fireblade a été relu après import, pas seulement chronométré. Pour chaque taille :

- nombre de lignes stockées **égal** au nombre de lignes écrites ;
- valeurs exactes aux positions testées (début, tiers, milieu, dernière ligne) ;
- format d'horodatage conservé sur **100 %** des lignes ;
- nombre d'hôtes distincts retrouvé (37) ;
- recherche de cinq motifs : 5,7 s sur 32 millions de lignes.

Aucun écart sur les cinq fichiers.

## Limites de ce comparatif

- TLE est piloté par sa fenêtre : le temps mesuré inclut son démarrage (2 à 3 s) et le
  rendu de la grille, ce qu'un import en ligne de commande n'inclurait pas. Le biais
  favorise TLE sur les petits fichiers, pas sur les gros.
- Aucun essai au-delà de 3,65 Go : au-delà de ~14 Go, TLE le dit lui-même, et Fireblade
  demanderait une machine avec plus de 32 Go pour rester dans les mêmes conditions.
- Une seule machine, un seul type de fichier (journal Linux aplati, colonnes de texte).

## Reproduire

`bench/bench.py` (Fireblade, avec génération et vérification), `bench/te_measure.ps1`
(Timeline Explorer, piloté depuis la session interactive via une tâche planifiée).
Les résultats bruts sont dans `bench/results-full.json` et `bench/tle-results.jsonl`.
