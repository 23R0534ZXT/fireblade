# Ajouts de présentation et d’import

Code du binaire : `358656b90eda57827116ae538488a010d31b86ed`.

- Barres de données sous les valeurs, dégradés de deux couleurs et indicateurs rouge/ambre/vert, avec bornes numériques explicites identiques entre les pages.
- Sauvegarde de ces règles dans les vues et bibliothèques globales Fireblade ; choix du mode et des bornes dans l’éditeur existant.
- Gras, italique, souligné et barré dans l’éditeur, la grille et la migration des styles de règles TLE compatibles.
- Préambules PeScan/Wisp reconnus après vérification de l’en-tête public exact. Aucune réécriture des sources ; leur SHA-256 inclut le préambule original.

Le rendu graphique travaille uniquement sur les cellules chargées. Il ne recalcule pas les bornes à partir d’une page visible ni ne lance de scan supplémentaire de tout le CSV. Les valeurs non numériques ou infinies restent sans dessin ; les valeurs hors bornes sont plafonnées pour le dessin uniquement. Les exportations CSV/XLSX conservent les données, sans exporter ces dessins.

La lecture des préambules est isolée dans `core/csv_preamble.py` ; la normalisation graphique dans `ui/visual_rules.py`. Les anciennes règles ont des valeurs par défaut et restent ouvrables.

Tests locaux : 276 réussites, 4 contrôles propres à Windows ignorés. Les tests couvrent le rendu QPainter dans une image, les propriétés du modèle Qt, le passage par l’éditeur, la persistance JSON, les bornes invalides et les préambules reconnus ou refusés. Les captures de vérification locale ne constituent pas des captures Windows.

## Écarts encore présents

Les variantes graphiques XML DevExpress (seuils automatiques, percentiles et jeux d’icônes propriétaires), les DLL .NET et les fonctions personnalisées arbitraires ne sont pas annoncées compatibles. Les attributs typographiques repris ne comprennent pas une police/taille individuelle par règle. La pause de premier affichage mesurée dans des qualifications antérieures demande encore un diagnostic. La parité exhaustive et l’usage manuel prolongé sous Windows 10/11 ne sont pas établis.

Le contraste des dégradés utilise la luminance relative des couleurs RGB linéarisées et choisit le meilleur rapport entre texte noir et blanc. Les cas de régression incluent jaune, vert saturé, bleu, gris sombre et blanc.

## Qualification du 31 octobre 2026

[Exécution réussie](https://github.com/23R0534ZXT/fireblade/actions/runs/41200337136) · [EXE publié](https://github.com/23R0534ZXT/fireblade/releases/tag/prototype-358656b90eda57827116ae538488a010d31b86ed).

Les suites Windows Python 3.11/3.12/3.13 ont chacune réussi 279 tests ; un test SMB est réservé au job de stockage séparé, dont les trois contrôles ont réussi. Le véritable EXE a passé 30 contrôles intégrés. Les huit variantes visuelles et les 42 contrôles sur le CSV existant de 3 GiB ont réussi. Le CSV a été réutilisé et son SHA-256 vérifié, sans régénération.

[Rapport de charge conservé](reports/358656b-3gib.json) : 2 441 216 enregistrements, import en 155,132 s ; dépliage de trois niveaux avec audit et page profonde en 4,494 s ; pic mémoire du processus de 448,1 Mio. Intervalle P95 du timer de 50 ms : 78 ms ; maximum : 2 875 ms. La pause après import n’est pas résolue : elle variait jusqu’à 14,953 s dans la qualification précédente. Ces résultats ne constituent pas une comparaison de vitesse avec TLE.

L’EXE publié, de 56 289 087 octets, a été téléchargé et comparé au binaire testé. SHA-256 : `1d25b92bb5e142d994f746f9ce25137aeb1315bafb151c9d45aa98be1f86d27f`. Les rapports sont automatisés, sur Windows Server ; les gestes physiques et l’usage prolongé Windows 10/11 restent à vérifier.
