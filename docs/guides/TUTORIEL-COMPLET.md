# Tutoriel complet — toutes les fonctionnalités de Fireblade

Ce tutoriel intégré décrit les parcours disponibles dans Fireblade 0.4, du premier import aux fonctions avancées de compatibilité Timeline Explorer, aux profils, aux règles, aux plugins .NET et aux analyses volumineuses. Il peut être ouvert sans fichier chargé depuis **Aide → Tutoriel complet**. Utilisez la table des matières et la recherche de la fenêtre pour retrouver une commande.

Fireblade est un explorateur local de CSV, TSV, TXT délimité, XLS et XLSX pour l’analyse forensic sur Windows. Il affiche une grille paginée avec recherche, filtres, tris, groupes, signets et notes. Les chemins décrits ci-dessous correspondent aux menus de l’application ; les commandes qui nécessitent une analyse sont désactivées tant qu’aucune base n’est ouverte.

## Table des matières

- [Parcours guidé](#parcours-guidé)
- [Démarrage](#démarrage)
- [Ouvrir des données](#ouvrir-des-données)
- [Rechercher et filtrer](#rechercher-et-filtrer)
- [Trier](#trier)
- [Regrouper](#regrouper)
- [Onglets et sessions](#onglets-et-sessions)
- [Signets et notes](#signets-et-notes)
- [Couleurs et détails](#couleurs-et-détails)
- [Enregistrer et exporter](#enregistrer-et-exporter)
- [Interrompre une opération](#interrompre-une-opération)
- [Colonnes dérivées et dates](#colonnes-dérivées)
- [Profils, supertimelines et plugins](#profils-supertimelines-et-compatibilité-tle)
- [Formats TLE, règles graphiques et expressions avancées](#mises-en-forme-graphiques-et-statistiques)
- [Thèmes, épinglage, hauteurs et pieds](#galerie-de-thèmes)
- [Référence de toutes les commandes](#référence-de-toutes-les-commandes)
- [Fidélité, stockage et limites](#fidélité-stockage-et-limites)

## Parcours guidé

Pour apprendre Fireblade sur un petit fichier sans toucher aux preuves, préparez un CSV de test avec une ligne d’en-tête et quelques lignes. Ouvrez-le avec **Fichier → Ouvrir un fichier**, puis effectuez ce parcours :

1. Recherchez un terme dans la barre **Rechercher**. Essayez ensuite un clic droit sur une cellule pour filtrer sur sa valeur.
2. Cliquez sur l’en-tête d’une date pour trier, puis utilisez **Affichage → Tri sur plusieurs colonnes** pour ajouter une seconde clé.
3. Glissez un en-tête dans la barre de groupement. Dépliez un groupe, parcourez ses pages, puis repliez-le.
4. Sélectionnez une ligne et ajoutez un signet avec une note. Utilisez **Détails** pour lire le contenu complet d’une cellule.
5. Enregistrez une vue avec **Ctrl+S**, changez la recherche, puis rechargez-la avec **Ctrl+L**.
6. Exportez le résultat filtré avec **Fichier → Exporter**, puis comparez-le à la source : l’export est une nouvelle destination.
7. Ouvrez **Affichage → Préférences** et essayez un thème. L’aperçu est annulable ; **OK** sauvegarde le choix.

Les sections suivantes détaillent chaque fonction et les cas où les données sont transformées, conservées ou refusées.

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

**Fichier → Exporter une session TLE (sources et signets)…** crée un `.tle_sess` référençant les fichiers sources originaux de tous les onglets et leurs signets, même masqués par un filtre. Les notes, vues et dispositions restent propres à Fireblade. Garder les sources aux chemins indiqués et installer les lecteurs nécessaires dans TLE. Une vérification d’intégrité lit les sources avant l’enregistrement ; elle peut être interrompue et ne réécrit pas les données. Les cas qui changeraient les tags sont refusés : source modifiée, même source ouverte dans plusieurs analyses, numéro de lecteur ambigu ou feuille Excel autre que la première. L’échec ou l’annulation conserve une session déjà présente à la destination. Voir [le contrat et les limites](../development/COMPATIBILITE.md#export-de-sessions-timeline-explorer).


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

### Régler les ressources

Pour modifier les ressources, éditer `%LOCALAPPDATA%\\Fireblade\\fireblade.toml` et redémarrer Fireblade. Les valeurs par défaut sont : mémoire DuckDB 256 Mio, 2 threads, pages de 250 lignes, fenêtre de 1000 lignes par parent, lots d’export de 2048 lignes et cache d’ordre activé pour les pages profondes.

```toml
[resources]
memory_mb = 256
threads = 2
page_size = 250
max_loaded_rows = 1000
export_batch_rows = 2048
cache_sorted_pages = true
```

`memory_mb` règle le buffer DuckDB et ne plafonne pas la mémoire totale de Fireblade. `max_loaded_rows` doit être un multiple de `page_size`. Les valeurs sont contrôlées au démarrage ; un réglage invalide apparaît dans le journal et Fireblade revient aux paramètres par défaut.

## Raccourcis

| Action | Raccourci |
|---|---|
| Ouvrir des données | Ctrl+O |
| Ouvrir une analyse | Ctrl+Maj+O |
| Exporter | Ctrl+Maj+E |
| Enregistrer / charger une vue | Ctrl+S / Ctrl+L |
| Enregistrer la session | Ctrl+Maj+S |
| Filtrer sur la valeur de la cellule active | Ctrl+Maj+F |
| Éditeur de filtres | Ctrl+Alt+F |
| Effacer les filtres | Ctrl+E |
| Déplier / replier les groupes | Ctrl+M / Ctrl+K |
| Marquer / retirer la sélection | Ctrl+Alt+B / Ctrl+Maj+M |
| Onglet suivant / précédent | Ctrl+Tab / Ctrl+Maj+Tab |
| Fermer l’onglet | Ctrl+W |
| Copier les lignes sélectionnées | Ctrl+C |
| Réinitialiser les largeurs de colonnes | Ctrl+R |
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

Le menu d’un en-tête propose le groupement des dates par année, trimestre, mois, semaine, jour, heure, minute ou seconde et un filtre calendrier. Le filtre d’un mois s’arrête au début du mois suivant, exclu. Les dates invalides apparaissent sous NULL dans les groupes temporels.

**Ctrl+K** replie les groupes et libère leurs descendants. **Déplier tous les groupes (vue paginée)** construit un index de toute la hiérarchie sur disque. Tous les groupes et enregistrements sont parcourables avec **Suivant/Précédent**, sans matérialiser des millions de lignes dans Qt. Le premier dépliage peut prendre du temps ; **Interrompre la requête** l’annule. Le repli rétablit l’arbre interactif.

## Colonnes épinglées, copie et export

Le menu d’un en-tête permet d’épingler une colonne à gauche, ou de la désépingler. La zone épinglée partage le même modèle et la même sélection ; elle ne charge pas une autre copie des données. Les colonnes épinglées apparaissent en premier dans les copies et exports, puis les autres colonnes visibles dans leur ordre. Masquer une colonne épinglée la retire également de la zone épinglée. **Ctrl+R** réinitialise les largeurs.

La case à cocher de la colonne Ligne/groupe marque une ligne sans demander de note ; les notes restent accessibles par double-clic et par le menu Édition. Une colonne source reconnue comme booléenne peut s’afficher en cases sans devenir éditable. Le menu de l’en-tête permet aussi de basculer cet affichage.

## Préférences et détails

**Affichage → Préférences** propose une galerie de 12 thèmes avec aperçu et règle le mode clair/sombre, la famille et taille de police, les dates reconnues (source, ISO, ISO à sept décimales), la position du panneau de détails, la copie des en-têtes et la copie immédiate au clic droit. **Maj+clic droit** conserve le menu contextuel lorsque la copie immédiate est active. Les préférences sont enregistrées dans `%LOCALAPPDATA%\Fireblade\preferences.json`.

Le détail et l’export conservent le texte source, même si la grille présente une date ou un booléen. Le format à sept décimales ne retire pas les décimales supplémentaires présentes dans la source. Le clic droit d’un champ du panneau Détails permet de copier sa valeur complète, la filtrer ou l’exclure. La fenêtre de cellule peut formater du JSON ou XML jusqu’à 2 Mo ; les DTD et entités XML sont refusées.

Le menu d’une cellule propose **Ouvrir avec** (programme choisi explicitement) et l’Explorateur pour les chemins existants sur ce poste. Il ne suit pas automatiquement les chemins des preuves vers un autre système.

## Profils, supertimelines et compatibilité TLE

**Affichage → Profils et plugins** affiche les schémas embarqués et installe des profils personnels JSON. **Appliquer le profil détecté** propose colonnes, dates, booléens et présentation. Le catalogue est décrit dans [la documentation des profils](../development/PLUGINS.md). Reconnaître un en-tête ne garantit pas tous les traitements du plugin Timeline Explorer correspondant. Les DLL C# TLE ne sont pas chargées.

La légende des supertimelines décrit les premières catégories de coloration des profils reconnus. Vérifier les valeurs de l’événement ; une couleur seule ne constitue pas une conclusion forensic.

**Analyse → Exporter/importer la disposition** partage une vue `.fireblade-view` entre analyses ayant exactement les mêmes colonnes. L’import accepte aussi certains layouts XML TLE pour l’ordre, les largeurs, l’épinglage à gauche/droite, les groupes et les tris. Les filtres et règles non compatibles provoquent un message explicite au lieu d’être ignorés.

**Fichier → Importer une session Timeline Explorer** lit un `.tle_sess`, vérifie ses sources et les réimporte dans de nouvelles bases, avec les tags. Les sources doivent être disponibles ; le CSV utilise sa BOM UTF-8/16/32 (UTF-8 en l’absence de BOM), les classeurs utilisent leur première feuille pour cette migration. Les dispositions locales du format sont retrouvées automatiquement à l’ouverture de chaque onglet. En cas d’échec ou d’annulation, les nouvelles bases de cette migration sont supprimées et l’analyse précédente est restaurée.

**Filtres → Expression textuelle** accepte une grammaire limitée et contrôlée : `Contains`, `StartsWith`, `EndsWith`, `IsNull`, `IsNullOrEmpty`, `In`, `Between`, comparaisons, `And`, `Or`, `Not`. Exemples : `Contains([User], 'alice') And [ID] >= 10` ; `[Date] >= #2026-01-01# And [Date] < #2026-02-01#`. Les expressions acceptent aussi fonctions imbriquées, calculs, `Iif`, `Upper`, `Substring`, `ToInt`, `Round`, `GetYear`, `AddDays`, `DateDiffDay` et les champs virtuels `Line`, `Tag`, `Note`. Les fonctions DevExpress non prises en charge sont refusées. L’éditeur ET/OU/NON permet de construire les conditions sans connaître cette syntaxe.

**Affichage → Messages** montre les 500 derniers messages de la session. Le journal de démarrage reste disponible séparément.

## Colonnes dérivées

**Analyse → Convertir une date…** : choisir la colonne, éventuellement une seconde colonne d’heure, le format source et le fuseau des dates sans décalage. Le résultat est une nouvelle colonne UTC à neuf décimales ; la source reste intacte. Formats : ISO, dates US/européennes, Unix s/ms/us/ns, FILETIME, WebKit, .NET et OLE. Les fuseaux IANA et Windows sont acceptés. Les heures locales suivent les conventions DST d’ICU ; pour lever une ambiguïté, fournir un décalage explicite.

**Ajouter une colonne calculée…** : saisir un nom et une expression, par exemple `Iif([Size] > 1024, 'large', 'small')`. La colonne est calculée par DuckDB et persistée dans l’analyse. **Contrôler les colonnes dérivées…** compte les valeurs NULL ; celles-ci peuvent indiquer une source vide, invalide ou hors plage. Aucun enregistrement n’est supprimé.

L’application d’un profil peut proposer ces colonnes normalisées, les catégories et les indicateurs MACB. Elles restent disponibles après réouverture et dans les exports.

## Préférences Timeline Explorer

**Fichier → Importer les préférences Timeline Explorer…** lit `Settings/TLE_settings.xml` : police, taille, copie des en-têtes, copie au clic droit, onglets sur plusieurs rangées, détails en haut/bas, format des dates et liste simple de colonnes épinglées. Les familles Office, Visual Studio, bleu, argent et contraste élevé sont associées aux thèmes Fireblade correspondants ; cette association adapte les couleurs et ne charge pas les skins DevExpress. Les champs inconnus ou structurés non traduits sont signalés dans Messages. Le fichier TLE reste intact. Les mêmes réglages sont modifiables dans les préférences Fireblade ; l’épinglage par défaut utilise un nom par ligne.

Les profils forensic reconnus s’appliquent automatiquement aux nouveaux imports, avant l’affichage de leurs colonnes. Désactiver **Appliquer le profil forensic reconnu à l’import** dans les préférences pour garder une grille générique. L’ajout d’une colonne dérivée conserve l’ordre, les largeurs, le masquage et l’épinglage des colonnes existantes.

## Mises en forme graphiques et statistiques

Dans **Analyse → Règles de coloration**, ajouter une règle et choisir la cible. L’onglet Apparence contient fond/texte, styles, police propre à la règle et classement, moyenne, valeurs uniques ou doublons. Pour une règle statistique sur toute la ligne, choisir explicitement son champ de valeurs. « Fond actif », « Texte actif » et « Police active » permettent de combiner plusieurs règles ; désactiver « Arrêter après cette règle » pour laisser les suivantes contribuer.

L’onglet Graphique propose barres, dégradés à deux/trois couleurs et icônes. Les bornes se choisissent indépendamment : fixes, automatiques, pourcentage de la plage ou percentiles exacts. Les calculs portent sur tout le résultat filtré, pas seulement la page. Le premier calcul peut prendre du temps ; les pages suivantes utilisent le cache. Les barres négatives disposent d’une couleur et d’un axe zéro ; les icônes ont trois à cinq niveaux avec seuils stricts ou inclusifs, couleurs et images personnalisables.

Les valeurs invalides restent sans graphique. Masquer les valeurs ne change ni les données, ni leur copie ou leur export. Les règles se conservent dans les vues et bibliothèques globales. CSV/XLSX exportent les données sans les dessins de la grille. Les règles XML standards des layouts TLE sont traduites ; toute adaptation est signalée.

## Plugins de lecture et fonctions TLE

**Fichier → Importer avec un plugin TLE (.NET)…** permet de choisir une DLL de lecteur et une source. **Analyse → Charger des fonctions .NET…** ajoute ses fonctions aux expressions, pour l’analyse active. Les fonctions déjà sélectionnées pour cette analyse se rechargent automatiquement, sous contrôle du registre local et de l’empreinte de la DLL. Utiliser l’import CSV natif pour les gros volumes habituels. Voir le [guide des plugins](../development/PLUGINS.md) pour les contrats et limites.


Les règles statistiques et graphiques proposent aussi un calcul sur toute la source, en ignorant le filtre actif. Les moyennes acceptent les comparaisons strictes ou inclusives. Les dates relatives utilisent `InDateRange([Date], 'Today')` et les périodes proposées dans l’éditeur de règles ; les jours sont calculés en UTC, les semaines commencent le lundi. L’import XML reprend les dates relatives combinées, les listes de valeurs et les douze styles texte/fond prédéfinis documentés de DevExpress. Les palettes prédéfinies sont adaptées ; les styles personnalisés peuvent être définis dans une bibliothèque JSON locale ou associée au layout ; voir [les exemples et limites](LAYOUTS-TLE.md). Un nom sans définition reste refusé.


**Affichage → Préférences → Personnaliser les couleurs** règle le fond des fenêtres, le texte, les champs, les lignes alternées et la sélection. « Rétablir les couleurs du thème » retrouve la palette du thème choisi dans la galerie (ou le thème standard si aucun modèle n’est choisi). Les règles d’icônes proposent aussi triangles, carrés, losanges, étoiles, classements et drapeaux ; les PNG personnels restent utilisables.


## Épingler une colonne à droite

Clic droit sur l’en-tête → **Épingler à droite**. La colonne reste visible à droite pendant le défilement horizontal. Les deux côtés peuvent être utilisés simultanément. Le même menu permet de déplacer la colonne à gauche ou de la désépingler. Masquer une colonne épinglée la retire aussi de son volet. Les vues, dispositions et sessions conservent le côté et la largeur ; copie et export placent les colonnes épinglées à droite en fin de tableau. Les layouts TLE `Fixed=Right` sont repris.

### Disposition automatique par format

À la fermeture ou au changement d’onglet, Fireblade enregistre un `.layout.local` dans `%LOCALAPPDATA%\Fireblade\Layouts\Local`. Les fichiers suivants de même format et de même schéma reprennent colonnes, largeurs, ordre, masquage, épinglage gauche/droite et vue : groupes, tris, filtres, recherche, résumés et couleurs. Les filtres mémorisés peuvent donc limiter les lignes visibles du nouveau fichier. Les sessions Fireblade conservent leur propre vue.

Vos XML TLE peuvent être placés dans `%LOCALAPPDATA%\Fireblade\Layouts\Default` ou `Layouts\Default` près de l’EXE : `<NomDuLecteur>.layout.local` est prioritaire sur `<NomDuLecteur>.layout`. Le nom du profil reconnu est également accepté (`EvtxECmd`, etc.). La disposition Fireblade mémorisée est prioritaire sur ces XML. Supprimez-la pour reprendre le XML ; supprimez les `.layout.local` pour reprendre le `.layout` par défaut. Une disposition invalide est signalée dans **Affichage → Messages**, sans bloquer l’import ni être écrasée à la fermeture. Les dispositions ne sont jamais enregistrées dans le dossier des preuves.

### Tris et styles importés de TLE

L’import XML reprend le tri par résumé de chaque niveau de groupe, y compris plusieurs critères, directions différentes et références par tag. La grille, le dépliage et l’export groupé gardent le même ordre. Dans **Résumés et tri des groupes**, changer le tri global ou les résumés remplace ces critères avancés ; accepter sans changement les conserve.

Les couleurs et polices de lignes, groupes, cellules et en-têtes sont conservées, ainsi que les alternances paires/impaires activées, la sélection, le focus, les alignements et dégradés. Les colonnes épinglées sont concernées. Les options conditionnelles explicites surchargent le style prédéfini au lieu de l’effacer entièrement. Les paramètres propres à DevExpress qui ne sont pas repris apparaissent dans les messages de migration.

### Fonctions .NET et objets complexes

Après import avec un lecteur DLL et chargement des fonctions, une expression comme `MaFonction([Details])` reçoit l’objet CLR réel, avec ses méthodes et son type d’origine. Les collections (`[Details.Children]`), membres imbriqués et retours d’autres fonctions sont aussi transmis par référence. Le JSON affiché dans la grille reste un aperçu, pas l’objet donné à la fonction.

Conservez la source et la DLL du lecteur : au premier appel après ouverture, Fireblade les vérifie puis relance le lecteur pour retrouver ses objets. Le contexte reste en mémoire jusqu’à la fermeture de l’analyse ; son volume dépend du lecteur tiers. Sans appel utilisant ces objets, le contexte n’est pas chargé. Une annulation le termine et l’appel suivant peut le reconstruire.

### Critères avancés

Exemples utilisables dans les filtres et règles de couleur :

```text
EventID=4624 And InRange(PID,1m,10000m)
[Items][[Amount]>[^.Limit]].Count()>0
[Groups].Sum([Children][[Amount]>[^.^.Limit]].Sum([Amount]))>100m
[Items][]
IsJanuary([Time]) And IsSameDay([Time],#!2026-01-02!#)
CharIndex('error',[Message],10)>=0
[Identifier]={513724e5-17b7-4ec6-abc4-0eae12c72c1f}
```

`^` remonte d’un contexte de collection ; on peut le répéter pour les collections imbriquées. Une restriction `[Items][condition]` est vraie dès qu’un élément convient. `[Items][]` teste si la collection est non vide. Les noms simples peuvent être écrits sans crochets ; `@Or` permet de viser une colonne portant un mot réservé. Les noms contenant des espaces restent entre crochets.

Les fonctions de calendrier suivent la convention UTC et les semaines commencent le lundi. `GetTimeOfDay` renvoie des ticks de 100 ns ; `AddTimeSpan` accepte des ticks ou une durée `[-][jours.]hh:mm:ss[.fffffff]`. La forme à trois arguments de `InDateRange` inclut la journée de fin ; `InRange` exclut sa borne supérieure. Les types de date seule et d’heure seule utilisent `#!…!#`.


## Pieds de groupes et hauteur des lignes

Dans **Affichage → Résumés et tri des groupes**, l’onglet **Par groupe** choisit les calculs, leur colonne de pied et le mode d’affichage des pieds : masqués, groupes dépliés ou toujours visibles. Un résumé placé dans l’en-tête reste à cet emplacement. L’onglet **Pied global** choisit des calculs indépendants portant sur tous les résultats filtrés. Les pieds de groupes gardent leurs propres apparences et ne constituent pas des lignes de données à marquer ou exporter.

**Affichage → Hauteur des lignes** permet d’adapter les lignes au texte affiché, de renvoyer le texte à la ligne et de régler les hauteurs de lignes, groupes et en-têtes. La hauteur automatique peut dépasser trois lignes ; les colonnes épinglées gardent le même alignement et le défilement permet de parcourir une ligne plus haute que la fenêtre. Seules les cellules déjà chargées sont mesurées. La grille affiche au plus 600 caractères par cellule ; utilisez les détails pour le contenu intégral.


## Galerie de thèmes

**Affichage → Préférences → Galerie de thèmes** propose Office clair/gris foncé/noir, Bleu classique, Argent, Graphite, Studio clair/sombre, Sable, Forêt et Contraste élevé clair/sombre. L’aperçu montre une petite grille, une sélection et des commandes. Il reste local au dialogue : **Annuler** conserve le thème de l’application. **OK** applique et sauvegarde le choix pour le prochain démarrage.

Choisir un thème de galerie rétablit sa palette ; **Personnaliser les couleurs** permet ensuite de la modifier. Changer manuellement de mode vers un mode différent de celui du thème revient à « Standard / personnalisé ». Les préférences restent défilables lorsque l’écran ou le zoom limite l’espace, avec OK/Annuler toujours accessibles.

Ces palettes et rendus sont des créations Qt de Fireblade. Les ressources, dessins et métriques propriétaires des skins DevExpress ne sont pas intégrés et l’identité visuelle avec Timeline Explorer n’est pas revendiquée.

## Référence de toutes les commandes

Cette liste sert d’index fonctionnel par menu. Les sections précédentes expliquent les gestes et les limites ; les liens vers les guides spécialisés donnent les contrats détaillés.

### Fichier

| Commande | Utilisation |
|---|---|
| Ouvrir un fichier | Importer CSV, TSV, TXT délimité, XLS ou XLSX. Plusieurs fichiers peuvent être choisis ; les imports suivants attendent dans la file séquentielle. |
| Importer avec un plugin TLE (.NET) | Choisir explicitement une DLL et son lecteur `ProcessFile` / `DataList`. Pour un lecteur reconnu, l’ouverture ordinaire peut aussi le détecter selon son en-tête. |
| Ouvrir une analyse | Reprendre un fichier `.timeline` existant. |
| Importer les préférences Timeline Explorer | Lire `Settings/TLE_settings.xml` et appliquer les propriétés prises en charge, avec compte rendu des adaptations. |
| Importer une session Timeline Explorer | Lire un `.tle_sess`, vérifier les sources et créer de nouvelles analyses avec les sources et tags. |
| Ouvrir / Enregistrer une session | Restaurer ou sauvegarder l’espace de travail Fireblade. La session référence les bases `.timeline` ; elle ne les emballe pas. |
| Exporter une session TLE (sources et signets) | Écrire un `.tle_sess` pour transmettre les références aux sources et les signets. Les notes, vues et dispositions Fireblade ne font pas partie de ce format. |
| Fermer l’onglet / Rouvrir le dernier onglet fermé | Fermer une analyse active ou restaurer son snapshot récent. |
| Vider la file d’ouverture | Retirer les imports en attente sans interrompre l’import en cours. |
| Exporter / Exporter les signets et notes | Exporter les lignes filtrées visibles ou les lignes annotées, avec CSV/XLSX et colonnes source d’annotation. |

### Édition

Copier les lignes sélectionnées ; ouvrir ou modifier le signet et la note d’une ligne ; marquer une sélection ; ajouter ou remplacer ses notes ; retirer ses signets. Les groupes ne sont pas des événements et ne marquent pas automatiquement leurs descendants.

### Affichage

| Commande | Utilisation |
|---|---|
| Regrouper / Colonnes | Choisir les niveaux de groupe, l’ordre et les colonnes visibles. Glisser-déposer les en-têtes reste possible. |
| Hauteur des lignes | Choisir des hauteurs fixes ou automatiques pour les lignes, groupes et en-têtes ; le calcul est partagé avec les volets épinglés. |
| Réinitialiser les largeurs | Restaurer la largeur initiale des colonnes. |
| Résumés et tri des groupes | Régler les calculs et tris de chaque groupe, les pieds de groupe et le pied global. Les résumés portent sur la population filtrée. |
| Déplier tous les groupes (vue paginée) / Replier tous les groupes | Parcourir l’arbre complet avec son index disque et des fenêtres bornées, puis revenir à l’arbre interactif. |
| Analyses ouvertes | Filtrer les onglets ouverts par nom ou chemin et activer une analyse. Une seule base est active à la fois. |
| Messages | Lire les diagnostics et les adaptations de layout/plugin récents. Jusqu’à 500 messages sont gardés pour la session. |
| Préférences | Régler thèmes et couleurs, police, formats de date, panneaux de détails, copie, onglets et épinglage par défaut. |
| Options de tri / Détails de la ligne | Afficher ou masquer ces panneaux. |
| Onglet suivant / précédent | Naviguer entre les documents ouverts. |
| Appliquer le profil détecté | Appliquer la présentation reconnue pour un format forensic, sans réécrire les valeurs sources. |
| Profils et plugins | Consulter le catalogue, installer des profils JSON et gérer les plugins approuvés. |
| Légende des supertimelines | Afficher les premières catégories/couleurs des profils de supertimeline reconnus. |
| Tri sur plusieurs colonnes | Construire un ordre avec plusieurs clés, type et direction. |

### Filtres

L’éditeur ET/OU/NON construit des arbres de critères ; Expression textuelle écrit le langage contrôlé ; Filtrer sur la cellule active utilise sa valeur ; Ajouter un filtre crée un filtre de colonne ; Effacer les filtres retire ceux de la vue ; Réinitialiser restaure la vue initiale et les règles globales ; Rechercher dans toutes les analyses inspecte tous les enregistrements des onglets ouverts et peut être interrompu.

### Analyse

| Commande | Utilisation |
|---|---|
| Enregistrer / Charger une vue | Persister ou réappliquer recherche, filtres, tris, groupes, résumés, colonnes et règles dans la base. |
| Exporter / Importer une disposition | Partager une vue Fireblade, ou importer/exporter le sous-ensemble compatible des layouts TLE. Le détail est dans le [guide des layouts](LAYOUTS-TLE.md). |
| Règles de coloration | Créer des conditions locales, statistiques et graphiques. Les règles locales sont prioritaires sur les règles globales. |
| Charger des fonctions .NET | Charger les fonctions approuvées d’un plugin pour les expressions de l’analyse. |
| Règles globales | Modifier, recharger, importer, remplacer, exporter la bibliothèque JSON et activer/désactiver son application pour la vue. |
| Surligner un texte | Mettre en évidence les occurrences correspondantes dans la grille. |
| Afficher la cellule / JSON | Lire le texte complet ou formater du JSON/XML sans modifier la source. |
| Provenance et SHA-256 | Consulter le chemin, la taille, le compte d’enregistrements et l’empreinte de la source. |
| Convertir une date | Créer une colonne UTC distincte à partir de formats standards ou d’horodatages forensic. |
| Ajouter une colonne calculée | Créer une vue SQL persistante depuis une expression. |
| Contrôler les colonnes dérivées | Compter les valeurs NULL produites par les conversions et expressions. |
| Interrompre la requête | Annuler un import, calcul, recherche, export ou annotation lorsqu’il est encore annulable. |

### Aide

**Tutoriel complet** ouvre ce document ; **Guide d’utilisation** ouvre le guide de prise en main ; **Licences** affiche les licences distribuées ; **À propos de Fireblade** affiche version et informations de construction.

## Fonctions avancées des règles

Les règles de coloration peuvent cibler une ligne, une cellule, une valeur ou une expression. Elles prennent en charge texte et fond, couleurs alpha, styles gras/italique/souligné/barré, police et taille propres à la règle, bordures et priorité. Les propriétés actives permettent de combiner plusieurs règles ; l’option d’arrêt contrôle si les règles suivantes sont évaluées.

Les règles statistiques proposent classement haut/bas, moyenne, valeurs uniques et doublons. Elles peuvent calculer sur la population filtrée ou toute la source, explicitement choisi, et travailler avec des seuils stricts ou inclusifs. Les règles graphiques proposent barres positives/négatives avec axe zéro, dégradés à deux ou trois couleurs, bornes fixes ou automatiques, pourcentages et percentiles exacts, ainsi que trois à cinq niveaux d’icônes. Les formes incluent indicateurs et images PNG ; les seuils, unités, planchers et priorités sont réglables.

Les valeurs invalides ne deviennent pas des nombres ou dates par approximation. Une règle statistique peut demander un calcul sur toute la source en ignorant le filtre actif. Les calculs peuvent nécessiter un premier parcours complet et de l’espace cache ; les affichages ultérieurs bénéficient du cache. Le CSV/XLSX exporte les valeurs, pas les dessins de la grille.

Les règles globales sont stockées dans `%LOCALAPPDATA%\\Fireblade\\regles-globales.json`. Elles sont associées aux noms de colonnes, peuvent être importées/exportées et rechargées depuis le disque. Chaque vue peut les désactiver ; les règles locales gardent priorité. Les fichiers JSON de profils et règles ne sont pas des programmes exécutables.

## Profils forensic, détection des lecteurs et transformations

Le catalogue embarqué contient des signatures et des noms de formats forensic issus des déclarations publiques de TLEFilePlugins. Il aide Fireblade à reconnaître les colonnes, présenter dates et booléens, réordonner les champs et proposer certaines règles. Il ne contient pas un parseur spécialisé pour chaque nom de format. Les exports déjà produits sont ouverts ; Fireblade ne lit pas directement les images disque, ruches de registre, EVTX ou fichiers Prefetch bruts.

Un profil JSON personnel peut définir un nom, une signature, les colonnes date/booléennes, un ordre, des règles et certaines transformations déclaratives. Dans **Affichage → Profils et plugins**, installez ou retirez ces profils. Ils ne peuvent pas contenir du code. Les champs inconnus restent présents ; une reconnaissance insuffisante revient à l’import générique.

Les transformations de profils peuvent créer des colonnes UTC, normaliser des champs temporels, produire des catégories/MACB ou calculer des valeurs scalaires. Elles restent des colonnes dérivées persistées dans l’analyse ; le fichier source reste intact. Consultez le [catalogue et son contrat](../development/PLUGINS.md).

Les lecteurs DLL TLE peuvent être installés dans `%LOCALAPPDATA%\\Fireblade\\Readers` ou le dossier `Readers` voisin de l’EXE. Fireblade détecte ceux qui publient un `ExpectedHeaders` correspondant. Si plusieurs lecteurs conviennent, il le signale ; l’import manuel permet de choisir. Une DLL présente seulement près du CSV n’est pas chargée automatiquement. Les lecteurs explicitement sélectionnés sont associés à l’analyse.

Les fonctions .NET exposées par `Name`/`Evaluate(object[])` s’utilisent dans les expressions par leur nom ou via `Custom`. Les adaptateurs `PluginText`, `PluginNumber`, `PluginBool` et `PluginDate` précisent le type de résultat. Les objets CLR complexes produits par le lecteur peuvent être transmis à des fonctions par référence, avec leurs types, méthodes et collections. Pour reconstruire le graphe à la réouverture, la source et la DLL doivent rester accessibles et identiques ; Fireblade contrôle les empreintes, le compte et la projection publique des valeurs. Une reconstruction qui ne redonne pas les valeurs importées est refusée. Les états privés arbitraires d’un lecteur ne sont pas sérialisés.

Le plugin s’exécute avec les droits de l’utilisateur dans un processus helper séparé ; ce processus n’est pas un bac à sable. Un lecteur tiers peut charger sa liste entière en mémoire. Utilisez l’import natif pour de grands CSV si le plugin n’est pas nécessaire. Voir [le guide des plugins](../development/PLUGINS.md).

## Dispositions et compatibilité Timeline Explorer

Les layouts `.layout.local` Fireblade mémorisent automatiquement colonnes, ordre, largeur, masquage, épinglage, groupes, tris, filtres, recherche, résumés et règles par profil et schéma. Une analyse Fireblade garde aussi ses vues. Les XML locaux/default peuvent être déposés dans les dossiers `Layouts/Local` et `Layouts/Default` du profil utilisateur ou dans les dossiers correspondants près de l’EXE. Une disposition Fireblade mémorisée est prioritaire ; une erreur de migration est affichée dans **Affichage → Messages** et le fichier reste intact.

L’import de XML TLE traduit les noms de champs connus, colonnes, filtres compatibles, recherche, groupements temporels, tris simples/multicritères, résumés, pieds, hauteurs, apparences et règles standards. Les images raster incluses sont décodées en image, sans interpréter de contenu sérialisé arbitraire ni suivre un chemin externe. Les styles personnalisés nommés doivent être disponibles dans une bibliothèque ; un nom sans définition n’est pas deviné.

**Analyse → Exporter une disposition** produit une disposition XML déclarative `XtraSerializer`. Elle peut contenir colonnes, filtres/groupes/tris/résumés, épinglage, apparences et règles représentables. Les fonctions propres à Fireblade sans traduction, populations statistiques non représentables et options nécessitant des données externes sont refusées ou signalées. Cette génération ne garantit pas que chaque export sera accepté par toute version TLE ; l’ouverture dans TLE reste une vérification distincte. Consultez [les formats et limites](LAYOUTS-TLE.md) et [le suivi de compatibilité](../development/PARITE-TIMELINE-EXPLORER.md).

Un `.tle_sess` importé vérifie les sources puis les copie dans de nouvelles bases Fireblade avec les tags. L’export `.tle_sess` décrit les sources et signets de tous les onglets ; il vérifie les sources, refuse les ambiguïtés et remplace sa destination atomiquement. Ni les vues ni les notes Fireblade ne se convertissent en tags TLE.

## Espace de travail avec de nombreux onglets

Les onglets peuvent s’afficher sur plusieurs rangées ; les préférences permettent de choisir cette présentation. La barre garde au plus trois rangées visibles et défile pour atteindre les autres. **Affichage → Analyses ouvertes** filtre et active une analyse ; **Ctrl+F** cherche dans toutes les analyses ouvertes. Chaque document inactif conserve un snapshot léger ; Fireblade garde une seule connexion de base active et recharge les pages à la réactivation.

Le parcours de qualification automatisé couvre 320 analyses distinctes, la recherche globale, les clics aux positions initiale, centrale et finale, ainsi que la sauvegarde/restauration de session. Cela documente la capacité du scénario ; les données de travail restent dans leurs bases séparées. Pour une session à reprendre, enregistrez-la et conservez à côté toutes les bases référencées.

## Fidélité, stockage et limites

Les valeurs source sont stockées comme texte pour préserver zéros initiaux, identifiants larges et contenu forensic. Les conversions ne modifient pas ces colonnes ; les résultats dérivés occupent de nouvelles colonnes. La provenance contient SHA-256 de la source. Fireblade vérifie que le fichier n’a pas changé pendant l’import.

Une analyse `.timeline` contient les données importées, vues, annotations et provenance. Une session Fireblade contient des références et réglages, pas les données. Les règles partagées et plugins approuvés sont séparés dans le profil Windows. Sauvegardez les bases, les sessions, les sources nécessaires, les profils et les bibliothèques que vous souhaitez transporter.

DuckDB travaille sur disque et la grille Qt ne charge que des pages ; les branches repliées libèrent leurs descendants. La fenêtre, le cache, les calculs statistiques, les lecteurs .NET et Qt ajoutent leur propre coût mémoire. Le réglage mémoire DuckDB n’est pas un plafond de mémoire du processus. Prévoyez de l’espace disque pour les bases, l’index de dépliage, les exports et les caches.

Le rapport Linux du moteur sur un replay de 15 GiB vérifie 12 206 080 enregistrements, pages initiales/finales, filtre, groupes et réouverture avec une limite de buffer DuckDB de 256 Mio. Le fichier répète cinq fois les enregistrements du CSV synthétique publié de 3 GiB. Ce parcours ne représente pas un plafond RAM total, une mesure Windows du véritable EXE, un benchmark TLE ou un test de chaque export réel. Les qualifications sont décrites dans [les rapports](../validation/20261101-compatibilite.md).

Les différences connues de compatibilité et les preuves manquantes sont suivies dans [l’inventaire des écarts](../development/ECARTS-TLE.md). Les thèmes de Fireblade sont des palettes Qt originales : les skins, polices, dessins et métriques propriétaires DevExpress ne sont pas intégrés. Les DLL TLE propriétaires, leurs dépendances et toutes les variantes d’export doivent être qualifiées sur leurs données réelles. Fireblade ne se présente pas comme certifié à parité complète avec Timeline Explorer.

## Raccourcis clavier — référence

| Action | Raccourci |
|---|---|
| Ouvrir des données / une analyse | Ctrl+O / Ctrl+Maj+O |
| Exporter les données | Ctrl+Maj+E |
| Enregistrer / charger une vue | Ctrl+S / Ctrl+L |
| Enregistrer une session | Ctrl+Maj+S |
| Filtrer sur la cellule active | Ctrl+Maj+F |
| Ouvrir l’éditeur de filtres | Ctrl+Alt+F |
| Effacer les filtres | Ctrl+E |
| Déplier / replier les groupes | Ctrl+M / Ctrl+K |
| Marquer / retirer la sélection | Ctrl+Alt+B / Ctrl+Maj+M |
| Chercher dans les analyses ouvertes | Ctrl+F |
| Analyse ouverte suivante / précédente | Ctrl+Tab / Ctrl+Maj+Tab |
| Fermer / rouvrir le dernier onglet | Ctrl+W / Ctrl+Maj+T |
| Copier les lignes sélectionnées | Ctrl+C |
| Guide d’utilisation | F1 |

Les raccourcis sont aussi disponibles depuis les menus ; les actions dépendant d’une analyse ne sont actives qu’après ouverture d’un fichier.
