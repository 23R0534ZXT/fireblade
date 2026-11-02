# Fireblade 0.6 — chasse IOC en masse

Vérifications locales sous Linux, Python 3.12.14, DuckDB 1.5.6, PySide6 6.12.0 et idna 3.11. L’interface Qt est testée hors écran ; cette validation ne qualifie pas l’EXE Windows.

La suite complète passe : **987 tests réussis, 28 ignorés**, en 162,05 secondes. Après les derniers ajustements de pagination et de barre de retour, les neuf contrôles ciblés de l’interface et de l’aide intégrée passent également.

Le scénario reproductible `python scripts/benchmarks/ioc_hunt.py` crée 100 000 lignes, trois colonnes et 50 000 domaines distincts à rechercher. Deux mesures locales : 0,64–0,65 seconde pour analyser la liste, 2,39–2,50 secondes pour lire les analyses. Les 100 000 champs correspondants et les deux lignes par indicateur sont vérifiés, y compris avec seulement 1 000 détails conservés. Le SHA-256 du CSV est revérifié après lecture. Ces durées dépendent du matériel, des types d’IOC et des valeurs ; elles ne prédisent pas celles d’une collecte réelle.

Les contrôles ciblés vérifient les frontières IPv4/IPv6, les sous-domaines et jokers, l’IDNA (`faß.de` distinct de `fass.de`), les URL sensibles à la casse du chemin, les empreintes de longueur exacte, les formes neutralisées, les rejets, les doublons et l’import UTF-16. Les tests de chasse utilisent de vraies bases DuckDB et vérifient les compteurs de champs et de lignes, les résultats négatifs, les filtres, les sources manquantes, les plafonds de détails, la réouverture des résultats et les exports CSV/XLSX.

Les tests de bureau parcourent deux analyses, sélectionnent un IOC sans correspondance, rétablissent toutes les occurrences et vérifient l’historique. Le saut vers la ligne source et le retour à la vue précédente sont exercés. Le transport du case réassocie les références tout en conservant les observations. Une annulation pendant la lecture supprime la nouvelle chasse et préserve la précédente ; un export annulé conserve sa destination précédente.

Les résultats négatifs concernent uniquement le périmètre importé et lu. Une source manquante donne un résultat partiel. Les détails sont plafonnés et les compteurs complets continuent au-delà du plafond. Une observation d’IOC ne prouve ni connexion ni compromission. Les analyses fermées absentes du case ne sont pas ajoutées automatiquement au transport des chasses.
