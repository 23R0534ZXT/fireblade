# Fireblade — prototype Windows

Explorateur de données forensic de bureau : CSV, TSV et XLSX.
Priorité actuelle : **Windows 64 bits**, interface classique et ressources maîtrisées.
Le projet reste un prototype ; le numéro du paquet ne constitue pas une validation de production.

## Utiliser le dossier portable

Dans l’onglet [Actions](https://github.com/23R0534ZXT/fireblade/actions), ouvrir une exécution réussie de **Windows native and portable**, puis télécharger l’artefact **Fireblade-Windows-x64**.
Il contient une archive à extraire entièrement. Lancer `Fireblade.exe` en gardant le dossier `_internal` à côté.
Python et les droits administrateur ne sont pas requis pour le portable.
L’artefact n’est publié par le workflow que si les tests des sources et les contrôles du véritable exécutable ont réussi.

`Verifier-Windows.cmd` relance des contrôles automatiques avec des données factices et écrit un rapport dans `%LOCALAPPDATA%\Fireblade\Verifications`.
Le rapport livré dans `verification-windows.json` décrit exactement les contrôles effectués lors de la construction.

## Lancer les sources

Installer **Python 3.12 64 bits**, puis double-cliquer sur `Lancer-Windows.cmd`.
Le lanceur accepte aussi Python 3.11 ou 3.13, choisit une installation 64 bits et prépare l’environnement `.venv` au premier lancement.
La première installation des dépendances nécessite Internet. L’application fonctionne ensuite localement.
Un fichier CSV, XLSX, `.timeline` ou `.fireblade-session` peut être déposé sur le lanceur ou dans la fenêtre.

## Construire sur Windows

Double-cliquer sur `Construire-Windows.cmd`.
Il prépare un environnement `.venv-build` dédié, crée le dossier portable, exécute le véritable `.exe` depuis un emplacement temporaire contenant espaces et accents, puis fabrique :

```text
dist\Fireblade-Windows-x64.zip
```

La construction échoue si le contrôle du portable échoue. Elle ne modifie ni les associations de fichiers ni la configuration système.
L’équivalent depuis un terminal Windows est `python -m scripts.build_windows`.

## Utilisation

- **Ouvrir un fichier** : confirmer où enregistrer l’analyse. Pour XLSX, choisir la feuille ; pour CSV, les options du séparateur et de l’encodage sont repliées par défaut.
- Chaque analyse s’ouvre dans un **onglet**. Ctrl+Tab change d’onglet, Ctrl+W le ferme. Seule la base de l’onglet actif reste ouverte : les autres conservent une petite copie de leur vue et de leur disposition.
- **Fichier → Enregistrer la session** conserve les onglets, filtres, tris, règles et colonnes dans un `.fireblade-session`. Ce fichier référence les analyses, il ne contient pas les données : garder les bases `.timeline` avec la session.
- Les analyses sont proposées dans `%LOCALAPPDATA%\Fireblade\Analyses`, pour pouvoir lire un CSV sur un support en lecture seule.
- Clic droit sur un en-tête : tri, type de tri, groupement, filtre et colonnes visibles.
- Clic droit sur une cellule : copie de la valeur, filtre rapide, exclusion ou note.
- Recherche globale avec Entrée ; filtres rapides par ET et **éditeur ET / OU / NON imbriqué** (Ctrl+Shift+F).
- Groupements à plusieurs niveaux par menu ou en glissant un en-tête dans la barre de groupement.
- **Tri sur plusieurs colonnes** : ordre, type et sens réglables par colonne.
- **Règles de coloration** : conditions identiques aux filtres, couleurs du fond/texte, gras, ligne entière ou cellule, priorité et activation. Elles sont calculées seulement pour les pages affichées.
- **Afficher la cellule / JSON** : texte brut ou JSON indenté sans réécriture de la source.
- **Appliquer le profil détecté** : premiers préréglages MFTECmd, EvtxECmd, PECmd, Hayabusa et Plaso L2T. Ce sont des dispositions de colonnes et tris, pas des parseurs d’artefacts ni une prise en charge de toutes les variantes.
- Les exports **CSV ou XLSX** portent sur tous les résultats filtrés, pas seulement la page chargée. XLSX utilise plusieurs feuilles au-delà de la limite Excel. Les valeurs sont écrites comme texte, y compris celles qui commencent par `=` ; les cellules trop longues sont refusées sans troncature.
- Les signets, notes et vues enregistrées restent dans la base `.timeline`.
- Si un nouvel import échoue ou est annulé, l’analyse précédente est rouverte avec sa vue et ses colonnes. Défilement et branches ouvertes ne sont pas restaurés.

Les valeurs sont stockées comme texte. Les conversions numériques exactes servent au tri et aux filtres, sans arrondir les identifiants Windows en flottants. UTF-8, UTF-16, Windows-1252 et Latin-1 sont disponibles. Les champs vides sont normalisés en NULL.
Les imports ambigus ou malformés sont signalés ; préciser le séparateur si la détection automatique n’est pas fiable.
Une validation finale déjà engagée peut finir malgré une demande d’annulation tardive. Une base vide peut rester après un import abandonné.

## Ressources et maintenance

Trois dépendances directes : **DuckDB**, **Qt Widgets via PySide6 Essentials** et **openpyxl** pour XLSX. Aucune dépendance à Excel, pandas, un serveur ou un navigateur embarqué.
La mémoire de buffer DuckDB est limitée à 256 MB par défaut, avec débordement sur disque.
Ce chiffre n’est pas un plafond de mémoire de tout le processus. Les pages sont bornées et les groupes repliés libèrent leurs descendants.
`fireblade.toml` règle mémoire, threads, taille des pages et cache de tri.
Les modules et points de modification sont décrits dans [le guide d’architecture](docs/ARCHITECTURE.md).

## Diagnostic Windows

En cas d’échec de démarrage du portable, consulter :

```text
%LOCALAPPDATA%\Fireblade\Journaux\demarrage.log
```

Le bootstrap garde un journal même si une bibliothèque Qt ou DuckDB ne se charge pas.
Le contrôle du portable couvre aussi les filtres imbriqués, le tri multi-colonnes, les couleurs de cellules, les onglets avec libération des connexions, la session et le parcours XLSX. Il vérifie la fenêtre Qt native Windows, les chemins accentués, un CSV UTF-8 BOM / CRLF en lecture seule, les groupes, les grands entiers, les filtres, l’export verrouillé puis repris, le presse-papiers Unicode, les signets après réouverture et l’annulation d’import avec restauration.
Il mesure aussi le working set du processus Windows. Ce contrôle ne valide pas l’Explorateur par un humain, les partages UNC, tous les chemins longs, une machine Windows vierge ou des exports forensic réels de plusieurs Go.
Les essais historiques du moteur sont conservés dans `docs/` ; ils ne doivent pas être utilisés comme preuve de validation Windows.

## Périmètre et compatibilité

Le nom visible et le portable sont **Fireblade**. Le paquet interne `timeline_next` et les bases `.timeline` restent compatibles. L’ancien `timeline-next.toml` est lu si `fireblade.toml` n’existe pas. Les anciennes analyses dans `%LOCALAPPDATA%\TimelineNext\Analyses` restent ouvrables ; elles ne sont pas déplacées automatiquement.

XLSX est lu progressivement, sans exécuter les formules. Les formules sont conservées sous leur texte, pas leur résultat calculé ; styles, zéros ajoutés par un format numérique et macros ne sont pas importés. Les anciens classeurs `.xls` ne sont pas encore pris en charge.

Le [suivi des fonctions](docs/PARITE-TIMELINE-EXPLORER.md) liste les fonctions présentes, partielles et restantes. Fireblade ne revendique pas encore la parité complète ni de meilleures performances mesurées face à Timeline Explorer.
