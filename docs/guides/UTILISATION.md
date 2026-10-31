# Utiliser Fireblade

Fireblade est un explorateur local de CSV, TSV, XLS et XLSX pour l’analyse forensic sur Windows. Il affiche une grille classique : recherche, filtres, tris, groupes, signets et notes.

## Démarrage

Télécharger `Fireblade.exe`, puis double-cliquer dessus. Python, Excel et un dossier de bibliothèques à côté du programme ne sont pas nécessaires. Le guide et les licences sont accessibles dans le menu **Aide**, même sans analyse ouverte.

Le programme prépare ses bibliothèques dans le dossier temporaire de Windows au démarrage. Cette étape peut prendre quelques secondes. Ce dossier est normalement supprimé à la fermeture. Les analyses sont enregistrées séparément pour conserver le travail.

## Ouvrir des données

1. Cliquer sur **Fichier → Ouvrir un fichier** ou appuyer sur **Ctrl+O**.
2. Choisir un CSV, TSV, TXT, XLS ou XLSX.
3. Confirmer le nom et l’emplacement du fichier d’analyse `.timeline`. Pour XLS/XLSX, sélectionner la feuille ; la première ligne doit contenir les noms de colonnes.
4. Attendre la fin de l’import. La source est lue sans réécriture.

Les exports CSV PowerShell avec une première ligne de métadonnées `#TYPE` sont acceptés. Une telle valeur au milieu des données reste un enregistrement normal.

Pour un CSV, les options permettent de préciser le séparateur et l’encodage : UTF-8, UTF-16, Windows-1252 ou Latin-1. Si la détection est ambiguë, sélectionner explicitement le séparateur. Les cellules vides sont normalisées en NULL.

Les valeurs sont conservées comme texte pour préserver les zéros initiaux et les grands identifiants. Les formules XLSX sont importées comme texte, sans calcul. Les styles et zéros provenant seulement d’un format numérique Excel ne sont pas importés. XLS est aussi pris en charge : les formules sont lues comme leurs résultats mémorisés ; les macros ne sont pas exécutées.

## Rechercher et filtrer

Saisir le texte dans **Rechercher**, puis appuyer sur Entrée. Cette recherche porte sur les colonnes de l’analyse active.

Un clic droit sur une cellule permet de filtrer sur sa valeur ou de l’exclure. Un clic droit sur un en-tête ouvre les filtres de colonne. Les filtres simples se combinent par ET ; un double-clic dans leur liste retire un filtre.

**Filtres → Éditeur ET / OU / NON** permet de construire des groupes imbriqués. Un groupe NON contient exactement une condition ou un groupe. Les opérateurs comprennent recherche textuelle, égalité exacte, regex RE2, cellules vides, comparaisons numériques et bornes de dates ISO. Les données dont la conversion numérique ou temporelle est impossible ne correspondent pas à cette comparaison.

**Réinitialiser** rétablit une vue par défaut, avec les règles globales activées.

## Trier

Cliquer sur un en-tête ou utiliser son menu contextuel. Choisir le type **Texte**, **Nombre** ou **Date ISO** selon les données.

**Affichage → Tri sur plusieurs colonnes** permet d’ordonner plusieurs clés. La première a priorité, puis les suivantes départagent les valeurs identiques. Les cellules NULL viennent en dernier. Les conversions numériques évitent les arrondis en flottants des grands identifiants.

## Regrouper

Glisser un en-tête dans la barre de groupement, ou choisir **Grouper par cette colonne** dans son menu. Plusieurs colonnes créent des niveaux imbriqués.

**Regrouper…** permet de sélectionner les colonnes et leur ordre. Déplier un groupe charge une page de ses enfants ; le replier libère les descendants chargés. Les comptages des groupes portent sur les résultats filtrés, pas seulement sur les lignes visibles.

Les boutons **Suivant** et **Précédent** parcourent les pages du niveau sélectionné. **Racine** permet de revenir au niveau principal. La pagination évite de charger toute l’analyse dans la grille.

## Onglets et sessions

Chaque analyse s’ouvre dans un onglet. **Ctrl+Tab** et **Ctrl+Shift+Tab** changent d’onglet ; **Ctrl+W** ferme l’onglet actif. Attendre ou interrompre une opération avant de changer d’analyse.

Seule la base de l’onglet actif reste ouverte. Revenir à un onglet restaure sa vue et ses colonnes, puis recharge les premières pages. La sélection, le défilement et les groupes dépliés ne sont pas conservés.

**Fichier → Enregistrer la session** conserve les références aux analyses, leur ordre, les vues et la disposition des colonnes dans un fichier `.fireblade-session`. Ce fichier ne contient pas les données : conserver les bases `.timeline` référencées. Une session dont une analyse manque ou a changé est signalée.

Les règles globales appartiennent au profil utilisateur : les exporter séparément si la session doit être partagée avec la même présentation.

## Signets et notes

Un double-clic sur une ligne ouvre son signet et sa note. Dans ce dialogue individuel, une note vide retire le signet.

Pour plusieurs lignes, utiliser Ctrl/clic ou Maj/clic, puis le menu **Édition** :

- **Marquer la sélection** ajoute un signet sans effacer une note existante ; une note vide reste possible.
- **Ajouter une note** ajoute le texte après la note existante, avec un saut de ligne.
- **Remplacer les notes** remplace explicitement leur contenu.
- **Retirer les signets** supprime les signets et leurs notes sur les lignes sélectionnées.

Les en-têtes de groupes sont ignorés : sélectionner un groupe seul ne marque pas automatiquement ses descendants. La case **Signets** limite la vue aux lignes marquées.

Les notes sont conservées dans l’analyse. La grille charge seulement les annotations des pages chargées.

## Couleurs et détails

**Analyse → Règles de coloration** définit les règles locales à la vue : conditions, couleurs du fond et du texte, gras, ligne ou cellule. La première règle correspondante a priorité.

**Analyse → Règles globales** gère les règles réutilisables, leur import/export JSON et leur rechargement. Elles suivent les noms des colonnes, même si leur ordre change. Une règle dont une colonne manque est ignorée et signalée dans la barre d’état. Les règles locales sont prioritaires. L’option **Appliquer à cette vue** permet de désactiver les règles globales pour cette vue seulement.

Le panneau **Détails** affiche les valeurs complètes et la note de la ligne. **Afficher la cellule / JSON** ouvre une cellule en texte brut ou en JSON indenté, sans modifier la source. Le formatage JSON est limité à 2 Mo ; le texte brut reste disponible.

**Affichage → Appliquer le profil détecté** propose de premiers préréglages MFTECmd, EvtxECmd, PECmd, Hayabusa et Plaso L2T. Ils organisent les colonnes et le tri ; ce ne sont pas des parseurs d’artefacts bruts.

## Enregistrer et exporter

Les signets et notes sont enregistrés dans `.timeline`. **Ctrl+S** enregistre une vue nommée dans cette analyse ; **Ctrl+L** la recharge.

**Fichier → Exporter** produit un CSV ou un XLSX des colonnes visibles dans leur ordre, pour tous les résultats filtrés, même si la grille n’en montre qu’une page. Pour une vue regroupée, choisir les lignes ou les comptages par groupe.

**Exporter les signets et notes** exporte les lignes marquées de la vue filtrée et ajoute trois colonnes : numéro d’enregistrement source, présence du signet et note. Le numéro correspond à l’ordre des enregistrements importés, hors en-tête ; un champ multiligne CSV peut occuper plusieurs lignes physiques.

XLSX écrit les valeurs comme texte, y compris celles qui commencent par `=`. Les résultats dépassant la capacité d’une feuille sont répartis sur plusieurs feuilles. Une cellule de plus de 32767 caractères provoque une erreur explicite : utiliser CSV pour conserver sa valeur complète.

Un export échoué ou annulé conserve l’ancien fichier de destination. La source et les analyses ouvertes ne peuvent pas servir de destination d’export.

## Interrompre une opération

Utiliser **Analyse → Interrompre la requête**. Une annulation d’import ou une erreur rouvre l’analyse précédente et sa vue. Une validation finale déjà engagée peut se terminer malgré une demande tardive. Une base vide peut rester après l’annulation d’un import.

L’annulation d’une annotation collective avant validation annule toute la sélection.

## Où se trouve le travail ?

Par défaut, Fireblade utilise le profil Windows :

- `%LOCALAPPDATA%\Fireblade\Analyses` : destination proposée pour les nouvelles analyses.
- `%LOCALAPPDATA%\Fireblade\regles-globales.json` : bibliothèque des règles globales.
- `%LOCALAPPDATA%\Fireblade\fireblade.toml` : configuration utilisateur facultative.
- `%LOCALAPPDATA%\Fireblade\Journaux\demarrage.log` : diagnostic de démarrage.

Les emplacements d’analyse, de session et d’export peuvent être choisis. Les sources peuvent se trouver sur un support en lecture seule. Sauvegarder les analyses et sessions utiles : supprimer ou remplacer l’exécutable ne supprime pas leur contenu.

## Raccourcis

| Action | Raccourci |
|---|---|
| Ouvrir des données | Ctrl+O |
| Ouvrir une analyse | Ctrl+Maj+O |
| Exporter | Ctrl+E |
| Enregistrer / charger une vue | Ctrl+S / Ctrl+L |
| Enregistrer la session | Ctrl+Maj+S |
| Éditeur de filtres | Ctrl+Maj+F |
| Marquer / retirer la sélection | Ctrl+M / Ctrl+Maj+M |
| Onglet suivant / précédent | Ctrl+Tab / Ctrl+Maj+Tab |
| Fermer l’onglet | Ctrl+W |
| Copier les lignes sélectionnées | Ctrl+C |
| Guide d’utilisation | F1 |

## En cas de problème

Si un import est refusé, vérifier le séparateur, l’encodage, l’en-tête ou la feuille sélectionnée. Un fichier déjà existant n’est pas écrasé lors de la création d’une analyse.

Si le programme ne démarre pas, consulter le journal de démarrage. Vérifier aussi que le profil utilisateur et le dossier temporaire Windows sont accessibles en écriture. Un fichier de règles invalide est laissé intact ; corriger et recharger, ou importer explicitement une bibliothèque valide.

Fireblade reste un prototype. Les tests automatisés ne remplacent pas les essais sur les exports réels de plusieurs Go et sur les postes d’enquête.

## Recherche entre fichiers et onglets

**Filtres → Rechercher dans toutes les analyses** ou **Ctrl+F** cherche dans les bases des onglets ouverts. Les comptages concernent tous leurs enregistrements, pas les pages chargées. Une option conserve les filtres et signets de chaque vue. Un double-clic sur un résultat ouvre l’analyse filtrée. Une erreur par fichier est affichée, sans omission silencieuse.

La recherche parcourt une analyse à la fois et peut être interrompue. **Affichage → Analyses ouvertes** filtre les noms ou chemins. **Ctrl+Maj+T** rouvre le dernier onglet fermé avec sa vue et ses notes. Les préférences permettent les onglets sur plusieurs rangées. Une fermeture conserve au maximum 20 snapshots.

La boîte Ouvrir accepte plusieurs fichiers. Les fichiers déposés pendant une opération attendent dans une file séquentielle. Chaque import conserve sa confirmation de destination ; annuler une confirmation passe au fichier suivant. **Fichier → Vider la file d’ouverture** retire les fichiers en attente sans interrompre l’opération courante.

## Résumés et périodes de groupement

**Affichage → Résumés et tri des groupes** ajoute des calculs : non vides, valeurs distinctes, somme, moyenne, minimum et maximum. Le type choisi s’applique au calcul ; les valeurs numériques ou dates invalides sont ignorées par leur conversion. Les comptes concernent tous les enregistrements filtrés. Trier par effectif, valeur ou résumé, en choisissant le sens ; l’export des groupes inclut les résumés.

Le menu d’un en-tête propose le groupement des dates par année, mois, jour ou heure et un filtre calendrier. Le filtre d’un mois s’arrête au début du mois suivant, exclu. Les dates invalides apparaissent sous NULL dans les groupes temporels.

**Ctrl+K** replie les groupes et libère leurs descendants. **Déplier tous les groupes (vue paginée)** construit un index de toute la hiérarchie sur disque. Tous les groupes et enregistrements sont parcourables avec **Suivant/Précédent**, sans matérialiser des millions de lignes dans Qt. Le premier dépliage peut prendre du temps ; **Interrompre la requête** l’annule. Le repli rétablit l’arbre interactif.

## Colonnes épinglées, copie et export

Le menu d’un en-tête permet d’épingler une colonne à gauche, ou de la désépingler. La zone épinglée partage le même modèle et la même sélection ; elle ne charge pas une autre copie des données. Les colonnes épinglées apparaissent en premier dans les copies et exports, puis les autres colonnes visibles dans leur ordre. Masquer une colonne épinglée la retire également de la zone épinglée. **Ctrl+R** réinitialise les largeurs.

La case à cocher de la colonne Ligne/groupe marque une ligne sans demander de note ; les notes restent accessibles par double-clic et par le menu Édition. Une colonne source reconnue comme booléenne peut s’afficher en cases sans devenir éditable. Le menu de l’en-tête permet aussi de basculer cet affichage.

## Préférences et détails

**Affichage → Préférences** règle le thème clair/sombre, la famille et taille de police, les dates reconnues (source, ISO, ISO à sept décimales), la position du panneau de détails, la copie des en-têtes et la copie immédiate au clic droit. **Maj+clic droit** conserve le menu contextuel lorsque la copie immédiate est active. Les préférences sont enregistrées dans `%LOCALAPPDATA%\Fireblade\preferences.json`.

Le détail et l’export conservent le texte source, même si la grille présente une date ou un booléen. Le format à sept décimales ne retire pas les décimales supplémentaires présentes dans la source. Le clic droit d’un champ du panneau Détails permet de copier sa valeur complète, la filtrer ou l’exclure. La fenêtre de cellule peut formater du JSON ou XML jusqu’à 2 Mo ; les DTD et entités XML sont refusées.

Le menu d’une cellule propose **Ouvrir avec** (programme choisi explicitement) et l’Explorateur pour les chemins existants sur ce poste. Il ne suit pas automatiquement les chemins des preuves vers un autre système.

## Profils, supertimelines et compatibilité TLE

**Affichage → Profils et plugins** affiche les schémas embarqués et installe des profils personnels JSON. **Appliquer le profil détecté** propose colonnes, dates, booléens et présentation. Le catalogue est décrit dans [la documentation des profils](../development/PLUGINS.md). Reconnaître un en-tête ne garantit pas tous les traitements du plugin Timeline Explorer correspondant. Les DLL C# TLE ne sont pas chargées.

La légende des supertimelines décrit les premières catégories de coloration des profils reconnus. Vérifier les valeurs de l’événement ; une couleur seule ne constitue pas une conclusion forensic.

**Analyse → Exporter/importer la disposition** partage une vue `.fireblade-view` entre analyses ayant exactement les mêmes colonnes. L’import accepte aussi certains layouts XML TLE pour l’ordre, les largeurs, l’épinglage à gauche, les groupes et les tris. Les filtres et règles non compatibles provoquent un message explicite au lieu d’être ignorés.

**Fichier → Importer une session Timeline Explorer** lit un `.tle_sess`, vérifie ses sources et les réimporte dans de nouvelles bases, avec les tags. Les sources doivent être disponibles ; le CSV utilise sa BOM UTF-8/16/32 (UTF-8 en l’absence de BOM), les classeurs utilisent leur première feuille pour cette migration. Les dispositions sont séparées. En cas d’échec ou d’annulation, les nouvelles bases de cette migration sont supprimées et l’analyse précédente est restaurée.

**Filtres → Expression textuelle** accepte une grammaire limitée et contrôlée : `Contains`, `StartsWith`, `EndsWith`, `IsNull`, `IsNullOrEmpty`, `In`, `Between`, comparaisons, `And`, `Or`, `Not`. Exemples : `Contains([User], 'alice') And [ID] >= 10` ; `[Date] >= #2026-01-01# And [Date] < #2026-02-01#`. Les expressions acceptent aussi fonctions imbriquées, calculs, `Iif`, `Upper`, `Substring`, `ToInt`, `Round`, `GetYear`, `AddDays`, `DateDiffDay` et les champs virtuels `Line`, `Tag`, `Note`. Les fonctions DevExpress non prises en charge sont refusées. L’éditeur ET/OU/NON permet de construire les conditions sans connaître cette syntaxe.

**Affichage → Messages** montre les 500 derniers messages de la session. Le journal de démarrage reste disponible séparément.

## Colonnes dérivées

**Analyse → Convertir une date…** : choisir la colonne, éventuellement une seconde colonne d’heure, le format source et le fuseau des dates sans décalage. Le résultat est une nouvelle colonne UTC à neuf décimales ; la source reste intacte. Formats : ISO, dates US/européennes, Unix s/ms/us/ns, FILETIME, WebKit, .NET et OLE. Les fuseaux IANA et Windows sont acceptés. Les heures locales suivent les conventions DST d’ICU ; pour lever une ambiguïté, fournir un décalage explicite.

**Ajouter une colonne calculée…** : saisir un nom et une expression, par exemple `Iif([Size] > 1024, 'large', 'small')`. La colonne est calculée par DuckDB et persistée dans l’analyse. **Contrôler les colonnes dérivées…** compte les valeurs NULL ; celles-ci peuvent indiquer une source vide, invalide ou hors plage. Aucun enregistrement n’est supprimé.

L’application d’un profil peut proposer ces colonnes normalisées, les catégories et les indicateurs MACB. Elles restent disponibles après réouverture et dans les exports.

## Préférences Timeline Explorer

**Fichier → Importer les préférences Timeline Explorer…** lit `Settings/TLE_settings.xml` : police, taille, copie des en-têtes, copie au clic droit, onglets sur plusieurs rangées, détails en haut/bas, format des dates et liste simple de colonnes épinglées. Le thème TLE est adapté au thème clair/sombre. Les champs inconnus ou structurés non traduits sont signalés dans Messages. Le fichier TLE reste intact. Les mêmes réglages sont modifiables dans les préférences Fireblade ; l’épinglage par défaut utilise un nom par ligne.

Les profils forensic reconnus s’appliquent automatiquement aux nouveaux imports, avant l’affichage de leurs colonnes. Désactiver **Appliquer le profil forensic reconnu à l’import** dans les préférences pour garder une grille générique. L’ajout d’une colonne dérivée conserve l’ordre, les largeurs, le masquage et l’épinglage des colonnes existantes.

## Mises en forme graphiques

Dans **Analyse → Règles de coloration**, ajouter une règle puis choisir une colonne cible, une condition et un mode : barre de données, dégradé ou indicateur à trois niveaux. Indiquer deux bornes numériques finies, minimum strictement inférieur au maximum. Les mêmes bornes s’appliquent à toutes les pages et aux exports de règles ; aucun calcul de minimum/maximum sur le seul écran visible n’est effectué.

Les barres sont dessinées sous le texte de la cellule. Le dégradé interpole la couleur Fond au minimum et la couleur Texte au maximum, avec un texte contrasté. Les indicateurs rouge/ambre/vert divisent l’intervalle en trois parties égales. Les valeurs hors intervalle sont ramenées aux extrémités pour le dessin ; les valeurs absentes, invalides ou infinies restent sans graphique. Les données originales ne sont pas modifiées. CSV/XLSX exportent les données ; ils ne reproduisent pas ces dessins de la grille.

Les règles se conservent dans les vues et bibliothèques globales Fireblade. Les variantes graphiques propriétaires des layouts TLE ne sont pas encore importées automatiquement.

Les exports PeScan/Wisp avec quatre lignes de préambule sont reconnus si leur en-tête correspond au schéma public attendu. Le préambule reste présent dans le fichier source et son SHA-256 est conservé.
