# Validation du lot de compatibilité du 1er novembre 2026

Les résultats ci-dessous sont locaux, sous Linux. Les contrôles Windows du commit et la comparaison avec l’application Timeline Explorer sont distincts.

| Parcours | Résultat | Portée |
|---|---|---|
| Pytest complet | 765 réussis, 6 ignorés, 301,42 s | Qt hors écran ; vrai helper .NET moderne disponible pour les tests CLR |
| Helpers | Moderne compilé et testé ; CLR4 compilé | CLR4 exécuté dans la qualification Windows, pas sur Linux |
| Corpus XML | 190 layouts publics, import et retour XML, empreintes épinglées | Schémas déduits des XML ; pas une qualification des données de chaque lecteur ni du rendu TLE |
| Tests amont des plugins | 227 réussis | Cas synthétiques et régressions fournis par le dépôt épinglé ; `RealOutputs` est un test explicite non exécuté faute de corpus réel |
| Pont .NET Fireblade | 207 variantes, 178 lecteurs, aucun échec | Les fichiers synthétiques produits par les tests amont passent dans le vrai helper puis DuckDB ; 3 lignes/variante, lignes source et intégrité vérifiées |
| Espace de travail | 320 analyses distinctes, 4 contrôles réussis | Imports, clics QtTest premier/milieu/dernier, recherche dans les 320, sauvegarde et restauration de la session |
| Gros CSV | 16 113 242 560 octets, 12 206 080 lignes, 6 contrôles réussis | Limite mémoire DuckDB 256 Mio ; ne représente pas une limite de mémoire totale du processus |

Le gros fichier contient une seule ligne d’en-tête suivie de cinq copies exactes des enregistrements du CSV publié existant de 3 GiB, vérifié par SHA-256. Les comptes de filtres et groupes sont calculés à partir de la référence indépendante publiée, multipliée par cinq. Le CSV de 3 GiB n’a pas été régénéré. Ce parcours contrôle les pages première/dernière, le filtre global, les groupes et la réouverture ; il ne revendique pas de test de tous les tris ou de tous les exports à cette taille.

Rapports :

- [Matrice des lecteurs](reports/20261101-tle-readers-linux.json)
- [320 analyses](reports/20261101-320-analyses-linux.json)
- [Moteur sur 15 GiB](reports/20261101-15gib-engine-linux.json)

Reproduction du parcours volumineux (optionnel, environ 40 GiB libres nécessaires pour fichier, analyse et marge de spill) :

```powershell
python -m scripts.qualify_large_replay --directory C:/FirebladeQA/replay --archive C:/FirebladeQA/Fireblade-test-3GiB.zip --report C:/FirebladeQA/replay-report.json
```

L’archive doit être celle du jeu publié ; son empreinte et celle du CSV extrait sont contrôlées. Le script refuse d’écraser un fichier de replay existant. Les fichiers de données ne sont pas ajoutés au dépôt.

La CI exige désormais en plus le parcours du véritable EXE avec 320 analyses et la matrice native des lecteurs. Aucun résultat Windows n’est déduit des rapports Linux. Les limites encore ouvertes sont détaillées dans [l’inventaire](../development/ECARTS-TLE.md).
