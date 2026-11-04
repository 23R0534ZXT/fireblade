# Utiliser Fireblade

Fireblade permet de parser un dossier d’artefacts, analyser ses EVTX avec Hayabusa et explorer les résultats avec leur contexte. Il ouvre aussi directement CSV, TSV, TXT délimités, XLS et XLSX, avec recherche, filtres, tris, groupes, signets et notes.

## Démarrage

Télécharger `Fireblade.exe`, puis double-cliquer dessus. Python, Excel et un dossier de bibliothèques à côté du programme ne sont pas nécessaires. Le guide et les licences sont accessibles dans le menu **Aide**, même sans analyse ouverte.

Pour la référence détaillée qui couvre toutes les commandes, règles, profils, thèmes et fonctions TLE, ouvrir **Aide → Tutoriel complet — toutes les fonctionnalités** ou lire le [tutoriel complet](TUTORIEL-COMPLET.md).

Le programme prépare ses bibliothèques dans le dossier temporaire de Windows au démarrage. Cette étape peut prendre quelques secondes. Ce dossier est normalement supprimé à la fermeture. Les analyses sont enregistrées séparément pour conserver le travail.

## Importer une collecte d’artefacts et lancer Hayabusa

La barre **Collecte** et **Analyse → Importer un dossier à parser…** permettent de choisir un dossier contenant des artefacts bruts. Les sous-dossiers sont parcourus ; les liens ne sont pas suivis. Le dossier de travail est créé sous `%LOCALAPPDATA%\Fireblade\Collectes`, séparément des preuves.

Avant de lancer les moteurs, choisissez l’organisation :

- **Un onglet par type d’artefact** : les fichiers d’un même type sont réunis, par exemple EVTX, Amcache ou Jump Lists. C’est le choix proposé par défaut.
- **Tout dans un seul onglet, regroupé par artefact** : une analyse « Collecte complète » est créée avec le groupement déjà appliqué sur la colonne d’artefact.

Les colonnes de formats différents sont réunies sans conversion de leurs valeurs ; les champs absents d’un format restent vides. Les colonnes homonymes ambiguës sont distinguées par un suffixe, et les champs de provenance ajoutés évitent les collisions avec les champs d’origine. Chaque ligne conserve son **Artefact**, son **Fichier source** et son **Parseur**. Les bases et sorties individuelles restent sur disque pour vérification ; seule l’organisation de la session change. Le choix et le groupement sont conservés à la reprise. Les anciennes collectes gardent leur disposition d’origine. Les alertes Hayabusa restent dans leur onglet dédié.

Le pack Windows construit depuis les sources épinglées comprend EvtxECmd, AmcacheParser, AppCompatCacheParser, PECmd, MFTECmd, RECmd, LECmd, JLECmd, SrumECmd, WxTCmd, RBCmd, RecentFileCacheParser et SQLECmd. RECmd utilise le batch Kroll et les 70 plugins de registre construits depuis RegistryPlugins ; EvtxECmd et SQLECmd disposent de leurs maps. Les CSV et TSV déjà produits peuvent aussi être importés. Il ne s’agit pas d’une prise en charge de chaque format forensic existant ni de tous les parseurs tiers.

Le bilan est une table triable avec une recherche et un filtre **Tous les fichiers**, **Réussis**, **Avertissements / à vérifier**, **Erreurs / interrompus** ou **Non reconnus / ignorés**. Sélectionnez un fichier pour lire ses avertissements, son SHA-256 et ses sorties. **Bilan complet** retrouve les informations générales ; **Ouvrir les résultats** ouvre le dossier de travail. La partie **1. Importer et parser** est distincte de **2. Détecter dans les EVTX Windows** ; Hayabusa reste désactivé si aucune collecte EVTX exploitable n’est prête.

L’onglet **Suivi des imports** conserve le bilan : fichiers traités, non reconnus, liens ignorés, erreurs et absence de sortie. Les CSV des moteurs restent dans `results`, les bases dans `analyses`, avec un manifeste `collection.json`, les journaux et une session `collection.fireblade-session`. Les sorties parsées ajoutent le chemin de l’artefact et le nom du parseur. Le plafond existant de 1000 analyses par session s’applique ; les sorties qui ne peuvent pas être chargées restent sur disque et sont signalées en erreur. Les empreintes des sources reconnues sont vérifiées avant et après traitement. Les moteurs absents ou en erreur ne sont jamais comptés comme réussis. Les journaux de transaction de registre LOG1/LOG2 sont conservés comme fichiers compagnons, utilisés par les lecteurs de ruches et non parsés comme des ruches indépendantes. Les moteurs EZ compilés désactivent leur télémétrie Exceptionless.

**Analyser la collecte avec Hayabusa** traite ensemble les EVTX inventoriés, après vérification et copie temporaire. Choisissez le niveau minimal dans l’onglet Collecte ; il vaut **Faible** par défaut. Fireblade utilise Hayabusa **4.3.1**, sa commande `dfir-timeline` et son profil verbose, sans assistant interactif ni téléchargement de règles pendant l’analyse. Les règles bruyantes, obsolètes et non prises en charge ne sont pas activées automatiquement.

L’onglet **Alertes Hayabusa.csv** devient une analyse Fireblade : filtrez Level, RuleTitle, Computer ou EventID, examinez RecordID, RuleID et les détails, puis ajoutez vos notes. `Fireblade_EVTX_Source` donne le chemin de l’EVTX original, ou une liste JSON pour une détection agrégée sur plusieurs fichiers ; EvtxFile correspond à la copie temporaire analysée. Les fichiers temporaires de travail sont retirés après exécution. Une analyse sans alerte est distincte d’une analyse en erreur ; le bilan indique les avertissements éventuels.

**Reprendre une collecte…** rouvre son dossier de travail. Conservez les artefacts sources pour relancer Hayabusa ; un EVTX modifié depuis l’inventaire est refusé. **Analyse → Interrompre la requête** interrompt aussi le moteur externe ; les résultats déjà terminés et leur bilan restent conservés. Chaque traitement externe a un délai maximal d’une heure. Les limites DuckDB ne plafonnent pas la mémoire des parseurs et de Hayabusa ; prévoyez aussi le disque nécessaire aux CSV, aux bases et aux copies temporaires des EVTX.

Le programme Windows embarque les moteurs, le runtime .NET, Hayabusa et les règles : l’utilisateur conserve un seul EXE pour le programme. Les résultats restent séparés dans le dossier de travail. Cette distribution est plus volumineuse et son extraction au démarrage demande davantage de disque temporaire. Les sources Hayabusa distribuées sont exportables depuis **Aide → Exporter les sources Hayabusa…** ; les licences restent dans **Aide → Licences**.

Une règle correspondante donne une piste, pas une preuve automatique de compromission. Hayabusa couvre ici les EVTX ; les autres artefacts sont parsés et explorables, sans prétendre leur appliquer les règles EVTX.

## Comprendre une alerte avec son contexte EVTX

L’onglet **Alertes Hayabusa** reste la liste courte des détections. Sélectionnez une alerte, choisissez la durée avant/après (5 minutes par défaut), puis cliquez **Voir le contexte de cette alerte**. La commande est aussi disponible au clic droit et dans **Analyse → Voir le contexte EVTX de l’alerte**.

Un panneau latéral réutilisable **Contexte EVTX de l’alerte** présente une chronologie des événements importés. La liste d’alertes reste ouverte. **Conserver ce contexte en onglet** enregistre une analyse consultable dans la session ; les aperçus non conservés ne sont pas ajoutés aux onglets et leurs fichiers temporaires sont retirés au remplacement ou à la fermeture. Le contexte contient : date, EventID, machine, canal, description et données détaillées. La colonne **Relation à l’alerte**, épinglée dans un contexte conservé en onglet, distingue :

- **Événement de l’alerte** : correspondance avec le fichier EVTX et EventRecordID, contrôlée aussi par la machine et l’EventID lorsqu’ils sont disponibles. La ligne apparaît en gras.
- **Référence candidate (agrégation)** : plusieurs références ne permettent pas d’attribuer chaque identifiant à un événement de façon certaine.
- **Proximité temporelle** : événement voisin sur la même machine, éventuellement dans un autre journal EVTX. Ce voisinage ne suffit pas à le déclarer suspect ou à établir une relation causale.

Le contexte est limité à 1000 événements, en conservant les références et les voisins les plus proches ; le résumé signale les limites ou sources indisponibles. La fenêtre est réglable de 1 minute à 24 heures avant et après. Une référence introuvable reste explicitement non résolue ; un événement proche ne la remplace pas silencieusement. Sans machine ou date exploitable, le voisinage n’est pas inventé.

Sélectionnez une ligne du contexte puis **Ouvrir l’événement EVTX source** pour retrouver exactement cette ligne dans la base EvtxECmd originale. **Effacer les filtres** retrouve les autres événements de ce fichier ; **Revenir aux alertes** ramène à la liste des détections et conserve ses filtres et annotations. Le panneau Détails et la fenêtre de cellule permettent de lire les charges utiles complètes, même si la grille les abrège.

L’aperçu est en lecture seule. Les contextes conservés en onglet sont des analyses Fireblade ordinaires : notes, signets, filtres et exports restent disponibles. Leur lien avec l’alerte est enregistré dans le dossier de travail ; leur ouverture retrouve automatiquement la collecte associée. Ils restent consultables avec les bases importées même si les EVTX originaux ne sont plus accessibles. Il s’agit des instantanés déjà parsés, sans reparsing ni réévaluation de la règle Hayabusa ; les sources restent nécessaires pour relancer la détection elle-même.


## Ouvrir des données

1. Cliquer sur **Analyse → Importer un fichier de données** ou appuyer sur **Ctrl+O**.
2. Choisir un CSV, TSV, TXT, XLS ou XLSX.
3. Confirmer le nom et l’emplacement du fichier d’analyse `.timeline`. Pour XLS/XLSX, sélectionner la feuille ; la première ligne doit contenir les noms de colonnes.
4. Attendre la fin de l’import. La source est lue sans réécriture.

Les exports CSV PowerShell avec une première ligne de métadonnées `#TYPE` sont acceptés. Une telle valeur au milieu des données reste un enregistrement normal.

Pour un CSV, les options permettent de préciser le séparateur et l’encodage : détection BOM, UTF-8, UTF-16, UTF-32, Windows-1252 ou Latin-1. Si la détection est ambiguë, sélectionner explicitement le séparateur. Les cellules vides sont normalisées en NULL.

Les valeurs sont conservées comme texte pour préserver les zéros initiaux et les grands identifiants. Les formules XLSX sont importées comme texte, sans calcul. Les styles et zéros provenant seulement d’un format numérique Excel ne sont pas importés. XLS est aussi pris en charge : les formules sont lues comme leurs résultats mémorisés ; les macros ne sont pas exécutées.

## Rechercher et filtrer

Saisir le texte dans **Rechercher**, puis appuyer sur Entrée. Cette recherche porte sur les colonnes de l’analyse active.

Sous chaque en-tête de données, le champ **Contient…** filtre directement cette colonne. Le filtre s’applique après une courte pause de saisie ou immédiatement avec Entrée. Plusieurs champs se combinent avec **ET** ; vider un champ retire son filtre « contient ». Les champs suivent les colonnes déplacées ou épinglées. **Filtres → Effacer les filtres** vide également ces champs.

Un clic droit sur une cellule permet de filtrer sur sa valeur ou de l’exclure. Un clic droit sur un en-tête ouvre les filtres de colonne. Les filtres simples se combinent par ET ; un double-clic dans leur liste retire un filtre.

**Filtres → Éditeur ET / OU / NON** permet de construire des groupes imbriqués. Les conditions sont présentées dans des cartes imbriquées : choisir **Toutes les conditions** (ET) ou **Au moins une** (OU). Chaque carte propose **+ Condition** et **+ Sous-groupe**, sans sélection préalable dans un arbre. Cocher **Exclure (NON)** inverse une condition ; **Inverser le groupe (NON)** inverse le bloc complet. Les libellés ET, OU et NON et les cadres imbriqués permettent de repérer les blocs. La phrase **Lecture du filtre** se met à jour pendant la saisie. **Replier / Déplier** réduit un groupe sans retirer ses conditions ; le résumé reste accessible. Les opérateurs comprennent recherche textuelle, égalité exacte, regex RE2, cellules vides, comparaisons numériques et bornes de dates ISO. Les données dont la conversion numérique ou temporelle est impossible ne correspondent pas à cette comparaison.

**Effacer les filtres**, près de la recherche, retire les recherches et critères sans changer les groupes, le tri, les couleurs ni les épinglages. **Affichage → Réinitialiser la vue** remet une vue par défaut, avec les règles globales activées.

## Trier

Les deux flèches à droite de chaque en-tête trient directement en ordre croissant (**▲**) ou décroissant (**▼**). La flèche active reste sélectionnée. Cliquer sur le nom de l’en-tête alterne aussi le sens ; le menu contextuel reste disponible. Choisir le type **Texte**, **Nombre** ou **Date ISO** selon les données.

**Affichage → Tri sur plusieurs colonnes** permet d’ordonner plusieurs clés. La première a priorité, puis les suivantes départagent les valeurs identiques. Les cellules NULL viennent en dernier. Les conversions numériques évitent les arrondis en flottants des grands identifiants.

## Regrouper

Glisser un en-tête dans la barre de groupement, ou choisir **Grouper par cette colonne** dans son menu. Plusieurs colonnes créent des niveaux imbriqués. La barre affiche ces niveaux sous forme de boutons numérotés reliés par des chevrons. Cliquer sur le **×** d’un bouton retire ce niveau en conservant les autres.

**Regrouper…** permet de sélectionner les colonnes et leur ordre. Déplier un groupe charge une page de ses enfants ; le replier libère les descendants chargés. Les comptages des groupes portent sur les résultats filtrés, pas seulement sur les lignes visibles.

Les boutons **Suivant** et **Précédent** parcourent les pages du niveau sélectionné. **Racine** permet de revenir au niveau principal. La pagination évite de charger toute l’analyse dans la grille.

## Onglets et sessions

Le panneau de navigation **Collectes et analyses** regroupe les résultats par collecte et artefact/famille ; sa recherche filtre les noms sans ouvrir les bases inactives. Cliquez une analyse pour l’activer. Le bouton **×** masque la navigation ; **Affichage → Navigation des analyses** la retrouve. Les onglets restent disponibles. Le bouton **Détails de la ligne**, près de Regrouper, replie ou affiche le panneau de détails.

Chaque analyse s’ouvre dans un onglet. **Ctrl+Tab** et **Ctrl+Shift+Tab** changent d’onglet ; **Ctrl+W** ferme l’onglet actif. Attendre ou interrompre une opération avant de changer d’analyse.

Seule la base de l’onglet actif reste ouverte. Revenir à un onglet restaure sa vue et ses colonnes, puis recharge les premières pages. La sélection, le défilement et les groupes dépliés ne sont pas conservés.

**Fichier → Enregistrer la session** conserve les références aux analyses, leur ordre, les vues et la disposition des colonnes dans un fichier `.fireblade-session`. Ce fichier ne contient pas les données : conserver les bases `.timeline` référencées. Une session dont une analyse manque ou a changé est signalée.

Les règles globales appartiennent au profil utilisateur : les exporter séparément si la session doit être partagée avec la même présentation.

**Fichier → Compatibilité Timeline Explorer → Exporter une session TLE (sources et signets)…** crée un `.tle_sess` référençant les fichiers sources originaux de tous les onglets et leurs signets, même masqués par un filtre. Les notes, vues et dispositions restent propres à Fireblade. Garder les sources aux chemins indiqués et installer les lecteurs nécessaires dans TLE. Une vérification d’intégrité lit les sources avant l’enregistrement ; elle peut être interrompue et ne réécrit pas les données. Les cas qui changeraient les tags sont refusés : source modifiée, même source ouverte dans plusieurs analyses, numéro de lecteur ambigu ou feuille Excel autre que la première. L’échec ou l’annulation conserve une session déjà présente à la destination. Voir [le contrat et les limites](../development/COMPATIBILITE.md#export-de-sessions-timeline-explorer).


## Signets et notes

Un clic dans la première colonne surligne toute la ligne et l’ajoute aux signets. Le repère est conservé dans la base et retrouvé après réouverture. Un nouveau clic retire le signet ; si une note existe, Fireblade demande confirmation avant de la supprimer. Un double-clic sur une cellule de données ouvre le signet et sa note. Dans ce dialogue individuel, une note vide retire le signet.

Pour plusieurs lignes, utiliser Ctrl/clic ou Maj/clic, puis le menu **Édition** :

- **Marquer la sélection** ajoute un signet sans effacer une note existante ; une note vide reste possible.
- **Ajouter une note** ajoute le texte après la note existante, avec un saut de ligne.
- **Remplacer les notes** remplace explicitement leur contenu.
- **Retirer les signets** supprime les signets et leurs notes sur les lignes sélectionnées.

Les en-têtes de groupes sont ignorés : sélectionner un groupe seul ne marque pas automatiquement ses descendants. La case **Signets** limite la vue aux lignes marquées.

Les notes sont conservées dans l’analyse. La grille charge seulement les annotations des pages chargées.

## Couleurs et détails

L’éditeur suit trois étapes : **1. Quand ?** pour les cartes de conditions, **2. Appliquer à** pour l’activation, la cible et l’arrêt après la règle, puis **3. Apparence** pour les couleurs ou graphiques. Dans Apparence, **Réglages avancés : statistiques et police** déplie les options supplémentaires. L’aperçu utilise une valeur d’exemple ; il ne vérifie ni la condition ni la distribution statistique de la source. Le surlignage des signets garde un fond uniforme sur toute la ligne, même lorsqu’une règle colore une cellule ; les règles ne sont pas supprimées.

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

Le menu d’un en-tête permet d’épingler une colonne à gauche ou à droite, de la déplacer de côté ou de la désépingler. Les deux volets partagent le même modèle et la même sélection ; ils ne chargent pas une autre copie des données. Les copies et exports ordonnent les colonnes épinglées à gauche, les colonnes centrales visibles, puis les colonnes épinglées à droite. Masquer une colonne épinglée la retire également de son volet. **Ctrl+R** réinitialise les largeurs.

La case à cocher de la colonne Ligne/groupe marque une ligne sans demander de note ; les notes restent accessibles par double-clic et par le menu Édition. Une colonne source reconnue comme booléenne peut s’afficher en cases sans devenir éditable. Le menu de l’en-tête permet aussi de basculer cet affichage.

## Préférences et détails

**Affichage → Préférences** sépare Apparence, Grille et copie, Dates et Compatibilité. La page Apparence propose une galerie de 24 thèmes avec aperçu et règle le mode clair/sombre, la famille et taille de police, les dates reconnues (source, ISO, ISO à sept décimales), la position du panneau de détails, la copie des en-têtes et la copie immédiate au clic droit. **Maj+clic droit** conserve le menu contextuel lorsque la copie immédiate est active. Les préférences sont enregistrées dans `%LOCALAPPDATA%\Fireblade\preferences.json`.

Le détail et l’export conservent le texte source, même si la grille présente une date ou un booléen. Le format à sept décimales ne retire pas les décimales supplémentaires présentes dans la source. Le clic droit d’un champ du panneau Détails permet de copier sa valeur complète, la filtrer ou l’exclure. La fenêtre de cellule peut formater du JSON ou XML jusqu’à 2 Mo ; les DTD et entités XML sont refusées.

Le menu d’une cellule propose **Ouvrir avec** (programme choisi explicitement) et l’Explorateur pour les chemins existants sur ce poste. Il ne suit pas automatiquement les chemins des preuves vers un autre système.

## Profils, supertimelines et compatibilité TLE

**Affichage → Profils et plugins** affiche les schémas embarqués et installe des profils personnels JSON. **Appliquer le profil détecté** propose colonnes, dates, booléens et présentation. Le catalogue est décrit dans [la documentation des profils](../development/PLUGINS.md). Reconnaître un en-tête ne garantit pas tous les traitements du plugin Timeline Explorer correspondant. Les lecteurs DLL compatibles peuvent être chargés via les helpers .NET ; voir la section Plugins de lecture et fonctions TLE pour leurs limites.

La légende des supertimelines décrit les premières catégories de coloration des profils reconnus. Vérifier les valeurs de l’événement ; une couleur seule ne constitue pas une conclusion forensic.

**Analyse → Exporter/importer la disposition** partage une vue `.fireblade-view` entre analyses ayant exactement les mêmes colonnes. L’import accepte aussi certains layouts XML TLE pour l’ordre, les largeurs, l’épinglage à gauche/droite, les groupes et les tris. Les filtres et règles non compatibles provoquent un message explicite au lieu d’être ignorés.

**Fichier → Compatibilité Timeline Explorer → Importer une session Timeline Explorer** lit un `.tle_sess`, vérifie ses sources et les réimporte dans de nouvelles bases, avec les tags. Les sources doivent être disponibles ; le CSV utilise sa BOM UTF-8/16/32 (UTF-8 en l’absence de BOM), les classeurs utilisent leur première feuille pour cette migration. Les dispositions locales du format sont retrouvées automatiquement à l’ouverture de chaque onglet. En cas d’échec ou d’annulation, les nouvelles bases de cette migration sont supprimées et l’analyse précédente est restaurée.

**Filtres → Expression textuelle** accepte une grammaire limitée et contrôlée : `Contains`, `StartsWith`, `EndsWith`, `IsNull`, `IsNullOrEmpty`, `In`, `Between`, comparaisons, `And`, `Or`, `Not`. Exemples : `Contains([User], 'alice') And [ID] >= 10` ; `[Date] >= #2026-01-01# And [Date] < #2026-02-01#`. Les expressions acceptent aussi fonctions imbriquées, calculs, `Iif`, `Upper`, `Substring`, `ToInt`, `Round`, `GetYear`, `AddDays`, `DateDiffDay` et les champs virtuels `Line`, `Tag`, `Note`. Les fonctions DevExpress non prises en charge sont refusées. L’éditeur ET/OU/NON permet de construire les conditions sans connaître cette syntaxe.

**Affichage → Messages** montre les 500 derniers messages de la session. Le journal de démarrage reste disponible séparément.

## Colonnes dérivées

**Analyse → Calculs et conversions → Convertir une date…** : choisir la colonne, éventuellement une seconde colonne d’heure, le format source et le fuseau des dates sans décalage. Le résultat est une nouvelle colonne UTC à neuf décimales ; la source reste intacte. Formats : ISO, dates US/européennes, Unix s/ms/us/ns, FILETIME, WebKit, .NET et OLE. Les fuseaux IANA et Windows sont acceptés. Les heures locales suivent les conventions DST d’ICU ; pour lever une ambiguïté, fournir un décalage explicite.

**Ajouter une colonne calculée…** : saisir un nom et une expression, par exemple `Iif([Size] > 1024, 'large', 'small')`. La colonne est calculée par DuckDB et persistée dans l’analyse. **Contrôler les colonnes dérivées…** compte les valeurs NULL ; celles-ci peuvent indiquer une source vide, invalide ou hors plage. Aucun enregistrement n’est supprimé.

L’application d’un profil peut proposer ces colonnes normalisées, les catégories et les indicateurs MACB. Elles restent disponibles après réouverture et dans les exports.

## Préférences Timeline Explorer

**Fichier → Compatibilité Timeline Explorer → Importer les préférences Timeline Explorer…** lit `Settings/TLE_settings.xml` : police, taille, copie des en-têtes, copie au clic droit, onglets sur plusieurs rangées, détails en haut/bas, format des dates et liste simple de colonnes épinglées. Les familles Office, Visual Studio, bleu, argent et contraste élevé sont associées aux thèmes Fireblade correspondants ; cette association adapte les couleurs et ne charge pas les skins DevExpress. Les champs inconnus ou structurés non traduits sont signalés dans Messages. Le fichier TLE reste intact. Les mêmes réglages sont modifiables dans les préférences Fireblade ; l’épinglage par défaut utilise un nom par ligne.

Les profils forensic reconnus s’appliquent automatiquement aux nouveaux imports, avant l’affichage de leurs colonnes. Désactiver **Appliquer le profil forensic reconnu à l’import** dans les préférences pour garder une grille générique. L’ajout d’une colonne dérivée conserve l’ordre, les largeurs, le masquage et l’épinglage des colonnes existantes.

## Mises en forme graphiques et statistiques

Dans **Analyse → Règles de coloration**, ajouter une règle et choisir la cible. L’onglet Apparence contient fond/texte, styles, police propre à la règle et classement, moyenne, valeurs uniques ou doublons. Pour une règle statistique sur toute la ligne, choisir explicitement son champ de valeurs. « Fond actif », « Texte actif » et « Police active » permettent de combiner plusieurs règles ; désactiver « Arrêter après cette règle » pour laisser les suivantes contribuer.

L’onglet Graphique propose barres, dégradés à deux/trois couleurs et icônes. Les bornes se choisissent indépendamment : fixes, automatiques, pourcentage de la plage ou percentiles exacts. Les calculs portent sur tout le résultat filtré, pas seulement la page. Le premier calcul peut prendre du temps ; les pages suivantes utilisent le cache. Les barres négatives disposent d’une couleur et d’un axe zéro ; les icônes ont trois à cinq niveaux avec seuils stricts ou inclusifs, couleurs et images personnalisables.

Les valeurs invalides restent sans graphique. Masquer les valeurs ne change ni les données, ni leur copie ou leur export. Les règles se conservent dans les vues et bibliothèques globales. CSV/XLSX exportent les données sans les dessins de la grille. Les règles XML standards des layouts TLE sont traduites ; toute adaptation est signalée.

## Plugins de lecture et fonctions TLE

**Fichier → Compatibilité Timeline Explorer → Importer avec un plugin TLE (.NET)…** permet de choisir une DLL de lecteur et une source. **Analyse → Calculs et conversions → Charger des fonctions .NET…** ajoute ses fonctions aux expressions, pour l’analyse active. Les fonctions déjà sélectionnées pour cette analyse se rechargent automatiquement, sous contrôle du registre local et de l’empreinte de la DLL. Utiliser l’import CSV natif pour les gros volumes habituels. Voir le [guide des plugins](../development/PLUGINS.md) pour les contrats et limites.


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

## Collectes Linux CatScale

Dans un case, utilisez **Importer un dossier de collecte…** pour choisir un dossier CatScale extrait ou contenant ses archives `catscale_*.tar.gz` / `FSecure_*.tar.gz`. Choisissez les onglets par famille ou la grille regroupée. Le parser est intégré sans dépendance Linux.

La colonne Lecture distingue les données structurées du texte brut conservé ; Source et Ligne gardent la provenance. Vérifiez les avertissements, binaires non pris en charge et limites avant de conclure que la collecte est complète. Hayabusa reste réservé aux EVTX Windows. Voir [le parcours complet et ses limites](TUTORIEL-COMPLET.md#importer-une-collecte-linux-catscale).

## Shellbags et WebCache

Importez le dossier contenant les ruches `UsrClass.dat` / `NTUSER.DAT` et la base ESE `WebCacheV01.dat`. Gardez les `.LOG1` / `.LOG2` de registre à côté de leur ruche. Le choix par artefact donne des onglets Shellbags et WebCache, avec les filtres, notes et sauvegardes du case.

Les références au registre, octets Shellbags, tables/containeurs WebCache et dates brutes sont conservés. Les avertissements signalent les ruches/bases sales ou éléments illisibles. Les dates de clé Shellbags ne sont pas des heures de visite certaines ; le lecteur WebCache ne rejoue pas les journaux ESE et ne récupère pas les données supprimées. Voir [les champs et limites du tutoriel](TUTORIEL-COMPLET.md#shellbags-et-webcache-windows).

## Chronologie et sauvegardes avancées

La version 0.5 ajoute un onglet **Chronologie & corrélations**, l’historique de
récupération des cases, les archives portables `.fireblade-case` et les rapports
HTML/PDF. Consultez le [guide détaillé](CHRONOLOGIE-ET-SAUVEGARDES.md) pour choisir
les dates, croiser les artefacts, récupérer une session et transporter une enquête.
