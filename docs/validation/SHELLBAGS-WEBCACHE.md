# Validation Shellbags et WebCache

Le [rapport local](reports/20261102-shellbags-webcache-linux.json) utilise deux artefacts publics épinglés par SHA-256 : la ruche UsrClass Windows 8.1 des tests Registry d’Eric Zimmerman et le WebCache de démonstration Plaso conservé dans les fixtures Sootmark/ese. Les copies compressées, leurs sources et licences sont dans `tests/fixtures/browser-artifacts`. Les sources originales et leurs empreintes sont aussi dans `config/forensic-browser-qa-fixtures.json`.

Le véritable hôte Shellbags, compilé avec Registry/ExtensionBlocks et ciblant win-x64, a été exécuté avec .NET 10 sous Linux. Il produit 523 lignes décodées, avec chemins, clés, valeurs, positions MRU, dates disponibles et octets bruts. L’empreinte source reste identique. Cette ruche est sale et n’a pas de journaux : son avertissement est attendu et obligatoire ; cela ne qualifie pas une récupération complète. RECmd peut refuser son passage registre séparé. Un autre NTUSER public sans Shellbags a aussi été lu sans inventer d’éléments.

Le lecteur ESE dissect.esedb produit 1 612 lignes non vides dans 23 sorties de tables, dont des métadonnées. Les tests vérifient une URL connue, son conteneur History, le FILETIME exact `130443534661252928` et sa conversion `2014-05-12T07:31:06.1252928Z`, les grands identifiants, données binaires, sentinelles, bases sales, tables illisibles et l’annulation.

Les résultats ont été importés dans de vraies bases DuckDB et affichés dans deux grilles Fireblade. Le contrôle compare les valeurs affichées aux lignes de la base et retrouve les notes après fermeture/réouverture du case. Les modes par sortie, par artefact et regroupé sont couverts pour WebCache.

Le contrôle `shellbags_webcache_real_parse_import_grid_case_restore` est obligatoire dans le véritable EXE Windows. Le rapport local et la compilation win-x64 ne sont pas une exécution Windows : les résultats Actions du commit téléchargé restent la preuve de cette qualification. La matrice historique des 13 EZ Tools reste distincte de cette nouvelle vérification.

Limites : lecture des clés actives, aucune récupération de données supprimées, aucun rejeu ESE, interprétation prudente des dates Shellbags. Voir [le tutoriel](../guides/TUTORIEL-COMPLET.md#shellbags-et-webcache-windows).
