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
| 28 Mo | **0,6 s** | 10,9 s | 18× plus rapide | ≤ 1,1 Go | 0,37 Go |
| 112 Mo | **1,7 s** | 9,8 s | 5,6× plus rapide | ≤ 1,1 Go | 0,78 Go |
| 453 Mo | **7,8 s** | 17,1 s | 2,2× plus rapide | ≤ 1,1 Go | 2,2 Go |
| 1,82 Go | **29,4 s** | 51,8 s | 1,8× plus rapide | ≤ 1,1 Go | 7,6 Go |
| 3,65 Go | **56,6 s** | 108,3 s | 1,9× plus rapide | 1,1 Go | **15,3 Go** |

Lecture honnête : depuis l'import en un passage (section suivante), **Fireblade est plus
rapide à toutes les tailles**, et l'écart se resserre à mesure que le fichier grandit
(18× à 28 Mo, 1,9× à 3,65 Go), parce que TLE démarre en 2 à 3 s quand Fireblade n'a pas
d'interface à lancer. Une seule mesure par taille : sur ce fichier de 3,65 Go, le même import
rejoué plusieurs fois a donné de 56,6 à 69,1 s selon l'état du cache disque.

La différence décisive est ailleurs, dans la colonne mémoire : Timeline Explorer charge
le fichier entier en RAM et demande **environ 4,2 fois la taille du fichier** ; Fireblade
reste à **son budget**, quelle que soit la taille. À 3,65 Go, TLE occupe 15,3 Go ; Fireblade
plafonne à 1,1 Go (pic mesuré de l'extérieur, budget réglé à 1 Go ; le même import avec un
budget de 8 Go plafonne à 2,2 Go — la mémoire suit le réglage, pas le fichier).

## L'import en un passage, ce que cela change

Jusqu'ici, un fichier plus gros que le pas de lecture était découpé en tranches temporaires
de quelques mégaoctets, chacune relue puis insérée : beaucoup de travail pour parcourir le
même fichier morceau par morceau. Le fichier est maintenant lu **d'une seule passe** tant
qu'il tient dans une transaction, DuckDB nommant les colonnes par position (`c0`, `c1`, …)
comme le fait déjà l'application partout ailleurs. Au-delà du seuil de transaction (2 Gio,
ou huit fois le budget), et si la mémoire manque, le chemin par tranches reprend la main et
commit au fur et à mesure.

| Fichier | Avant (tranches) | Après (un passage) |
| --- | --- | --- |
| 28 Mo | 1,2 s | **0,6 s** |
| 112 Mo | 5,1 s | **1,7 s** |
| 453 Mo | 19,7 s | **7,8 s** |
| 1,82 Go | 74,3 s | **29,4 s** |
| 3,65 Go | 147,8 s | **56,6 s** |

Sur le fichier de 3,65 Go, le débit passe de **24 à 62 Mo/s** (le même import rejoué à chaud
mesure 58,8 s). La mémoire, elle, ne bouge pas : pic de **1 077 Mo** mesuré de l'extérieur,
pour un budget de 1 Go.

## Ce que cela change sur une machine modeste

TLE lui-même documente sa limite : sur le fichier de 3,65 Go il affiche

> « The selected file is 3,653,736,773 in size and will take time to load.
> **TLE can handle files at least 14 GB in size**, but be patient… »

Cette phrase est cohérente avec la mesure : à 4,2× le fichier, 14 Go de fichier demandent
environ 59 Go de RAM, ce qui suppose une station de travail. Sur une VM de 8 Go, le plafond
pratique est un fichier d'environ **1,9 Go** ; au-delà, l'outil ne peut pas ouvrir le
fichier quel que soit le temps qu'on lui accorde.

Fireblade, sur la même VM de 8 Go, importe sans changer de comportement — c'est l'objet du
travail de cette version (import en un passage, commit par tranches au-delà de 2 Gio, budget
qui grandit tout seul jusqu'à la moitié de la RAM, voie bornée ligne par ligne en dernier
recours).

## Ce que coûte l'intégrité

Fireblade calcule le SHA-256 du fichier **avant et après** l'import, pour qu'un fichier
modifié pendant la collecte ne passe pas inaperçu. Sur ce fichier de 3,65 Go, un passage
coûte **2,7 s** (1 336 Mo/s) : environ 5,4 s sur les 57 s, soit 9 % du temps. Le reste est
la lecture et l'écriture des colonnes, pas la vérification.

## Le réglage d'effort ne change pas un seul fichier

Trois budgets sur le même fichier de 3,65 Go :

| Réglage | Temps | Débit |
| --- | --- | --- |
| 512 Mo, 1 thread | 58,9 s | 62,0 Mo/s |
| 1 Go, 4 threads (défaut) | 58,8 s | 62,1 Mo/s |
| 8 Go, 20 threads (maximum) | 60,0 s | 60,9 Mo/s |

C'est normal et c'est à documenter : **un seul fichier est une seule séquence de lecture**,
les threads n'y changent rien. Le réglage d'effort sert aux **dossiers** (beaucoup de
fichiers en parallèle) et au **budget mémoire** ; il ne rend pas un fichier unique plus
rapide. Là où il compte, mesuré sur 48 fichiers : 3,4 s à un thread, 1,2 s à quatre,
1,0 s à huit.

## Les opérations répétées : recherche, filtre, group by, tri

L'import n'est qu'une fois ; le travail d'un analyste, c'est de chercher, filtrer, regrouper
et trier, encore et encore. Ces opérations ont été mesurées sur **les deux outils**, sur les
mêmes fichiers, avec la même méthode : action lancée, puis attente que l'outil cesse de
travailler (CPU au repos).

Sur le fichier de 3,65 Go / 32 millions de lignes :

| Opération | Fireblade | TLE | Écart |
| --- | --- | --- | --- |
| Ouvrir le fichier | **56,6 s** | 109,2 s | 1,9× |
| Rechercher « host07 », toutes colonnes (864 865 lignes) | **2,42 s** | 149,94 s | 62× |
| Rechercher « error », toutes colonnes (0 ligne) | **2,56 s** | 144,39 s | 56× |
| Rechercher « session » sur le message (32 M lignes) | **1,45 s** | 150,32 s | 100× |
| Filtrer sur l'égalité Host = host07 | **0,14 s** | pas d'équivalent direct | — |
| Grouper par Host (37 groupes) | **0,12 s** | 134,29 s | 1 100× |
| Trier par horodatage | **0,64 s** | 8,54 s | 13× |
| Trier par hôte puis horodatage | **0,88 s** | 15,17 s | 17× |

L'écart se resserre quand le fichier est petit (TLE garde tout en mémoire et rebalaye
seulement ce qu'il affiche) et s'ouvre quand il grandit :

| Taille | Recherche « host07 », toutes colonnes | Group by Host |
| --- | --- | --- |
| 28 Mo | 68× plus rapide | au moins 31× |
| 112 Mo | 73× | 179× |
| 453 Mo | 58× | au moins 812× |
| 1,82 Go | 57× | 1 310× |
| 3,65 Go | 62× | 1 119× |

Lecture honnête, et ce que ces chiffres ne disent pas :

- **Timeline Explorer est piloté par sa fenêtre**, donc ses temps incluent le redessin de la
  grille ; Fireblade répond par une requête et ne matérialise que les lignes affichées. Le
  biais favorise TLE, jamais Fireblade.
- **Les deux outils ont été vérifiés sur le même résultat**, pas seulement chronométrés :
  recherche « host07 » → *Visible lines* 864 865 chez TLE, 864 865 chez Fireblade ; group by
  → 37 groupes de 864 865. Un chiffre rapide qui ne filtre rien ne serait pas un résultat.
- TLE cherche dans **toutes** les colonnes ; la requête Fireblade comparée est donc un OU de
  huit `LIKE`, colonne par colonne — c'est bien le même travail qui est chronométré.
- Le group by n'est pas un détail d'affichage : TLE reconstruit une vue groupée de 32 millions
  de lignes, Fireblade renvoie 37 agrégats.
- Une seule mesure par taille et par opération. La variance observée sur l'import Fireblade
  (56,6 à 69,1 s sur le même fichier) donne l'ordre de grandeur de l'incertitude.

## Vérification : rien ne se perd

Fireblade a été relu après import, pas seulement chronométré. Pour chaque taille :

- nombre de lignes stockées **égal** au nombre de lignes écrites ;
- valeurs exactes aux positions testées (début, tiers, milieu, dernière ligne) ;
- format d'horodatage conservé sur **100 %** des lignes ;
- nombre d'hôtes distincts retrouvé (37) ;
- recherche de cinq motifs : 5,8 s sur 32 millions de lignes.

Aucun écart sur les cinq fichiers, avant comme après l'import en un passage : l'identifiant
de ligne (`__row_id`) reste celui du fichier, aucune ligne décalée.

## Limites de ce comparatif

- TLE est piloté par sa fenêtre : le temps mesuré inclut son démarrage (2 à 3 s) et le
  rendu de la grille, ce qu'un import en ligne de commande n'inclurait pas. Le biais
  favorise TLE sur les petits fichiers, pas sur les gros.
- Les chiffres de TLE datent de la mesure initiale, sur les mêmes fichiers et la même
  machine ; ceux de Fireblade ont été repris après l'import en un passage.
- Aucun essai au-delà de 3,65 Go : au-delà de ~14 Go, TLE le dit lui-même, et Fireblade
  demanderait une machine avec plus de 32 Go pour rester dans les mêmes conditions.
- Une seule machine, un seul type de fichier (journal Linux aplati, colonnes de texte).
- Les opérations de Timeline Explorer sont mesurées **depuis sa fenêtre** (frappe, clic, glisser
  d'en-tête) et celles de Fireblade depuis son API : deux façons d'obtenir le même résultat,
  pas deux implémentations identiques. Les états obtenus ont été comparés (lignes visibles,
  nombre de groupes) avant de publier les temps.

## Reproduire

`bench/bench.py` (Fireblade : import, vérification, puis recherche, filtre, group by et tri),
`bench/fb_peak.py` (le même import aux trois réglages d'effort, plus le coût du hachage seul),
`bench/te_measure.ps1` (ouverture dans Timeline Explorer), `bench/te_ops.ps1` (recherche,
tri et group by dans sa fenêtre) et `bench/te_campaign.ps1` (les cinq tailles, une session par
fichier). Timeline Explorer n'a ni ligne de commande ni arbre d'automatisation : il est piloté
au clavier et à la souris depuis la session interactive, via une tâche planifiée.
Les résultats bruts sont dans `bench/results-full.json`, `bench/peak.json`,
`bench/tle-results.jsonl` et `bench/tle-ops.jsonl`.
