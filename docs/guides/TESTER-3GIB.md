# Tester Fireblade avec le CSV de 3 Go

Le jeu est téléchargeable dans la [Release dédiée aux données](https://github.com/23R0534ZXT/fireblade/releases/tag/test-data-3gib). Le générateur est [scripts/windows/dataset.py](../../scripts/windows/dataset.py). Le code de l’application, du générateur et des tests est sur `main`.

## Télécharger et ouvrir

1. Télécharger [Fireblade-test-3GiB.zip](https://github.com/23R0534ZXT/fireblade/releases/download/test-data-3gib/Fireblade-test-3GiB.zip), puis l’extraire avec Windows.
2. Lancer `Fireblade.exe`. La [construction déjà qualifiée avec ce jeu](https://github.com/23R0534ZXT/fireblade/releases/tag/prototype-fcb1390f818b36699acba67b229fb45215e4f62f) est disponible séparément ; le programme reste un fichier unique.
3. Cliquer sur **Ouvrir un fichier**, choisir `Fireblade-test-3GiB.csv`, puis confirmer la destination de l’analyse `.timeline`.

Prévoir au moins **12 GiB libres** pour conserver le CSV extrait, l’analyse, les temporaires de tri et un export complet. Le ZIP n’est pas un CSV réduit : après extraction, le fichier mesure **3 222 648 632 octets** et contient **2 441 216 enregistrements** sur **18 colonnes**. Certains champs sont multilignes, donc compter les lignes physiques du fichier ne donne pas le nombre d’enregistrements.

Les données sont fictives : artefacts, dates, utilisateurs, machines, chemins, commandes enregistrées sous forme de texte, grands identifiants, Unicode, JSON, cellules vides et champs avec guillemets.

## Quelques essais avec résultats attendus

Réinitialiser la vue entre les essais indépendants.

| Essai | Action | Résultat attendu |
|---|---|---|
| Import | Ouvrir le CSV complet | 2 441 216 enregistrements |
| Regroupement simple | Clic droit sur `Artifact` → **Grouper par cette colonne** | 8 groupes de 305 152 enregistrements chacun |
| Trois niveaux | Ajouter `User`, puis `Computer` au groupement par leurs menus d’en-tête | Dépliage progressif des trois niveaux ; les comptages des parents restent cohérents |
| Filtre exact | Ajouter un filtre sur `User`, égalité exacte, valeur `user042` | 9 405 enregistrements |
| Recherche | Rechercher `Enregistrement 137,` puis appuyer sur Entrée | 1 enregistrement, numéro source 138 |
| Grand entier | Trier `RecordID` en type **Nombre**, croissant | Première ligne : numéro source 2, valeur `9007199254740994` ; les valeurs invalides ou vides viennent à la fin |
| Signets | Sélectionner deux lignes de données, les marquer, puis cocher **Signets** | 2 enregistrements ; les signets restent présents après réouverture de l’analyse |
| Export complet | Réinitialiser et exporter en CSV sans colonnes d’annotations | 2 441 216 enregistrements ; sur ce jeu canonique, même taille et même SHA-256 que le CSV téléchargé |

Le champ `reference` du manifeste `dataset.json` fournit d’autres comptages indépendants, notamment les utilisateurs vides et les filtres combinés. Ce [manifeste est aussi versionné sur main](../validation/datasets/3gib.json).

## Vérifier le téléchargement

Le fichier [SHA256SUMS.txt](https://github.com/23R0534ZXT/fireblade/releases/download/test-data-3gib/SHA256SUMS.txt) contient les empreintes du ZIP et du CSV extrait. Pour le CSV, PowerShell peut calculer l’empreinte ainsi :

```powershell
Get-FileHash ".\Fireblade-test-3GiB.csv" -Algorithm SHA256
```

Empreinte attendue du CSV :

```text
2382777d3917a973a1e5104b3bc404d02d3901aeff8104d34fc30e4264776cf0
```

Le contenu correspond au fichier utilisé dans [la qualification Windows réussie](https://github.com/23R0534ZXT/fireblade/actions/runs/41091670266). Les limites et les commandes de reproduction du parcours automatisé sont décrites dans [QUALIFICATION.md](../validation/QUALIFICATION.md).
