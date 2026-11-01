# Compatibilité et transformations

Le moteur est Python + DuckDB + Qt. Un hôte .NET autonome exécute les lecteurs TLE installés reconnus par en-tête et les fonctions choisies par l’utilisateur. Aucun serveur ni `eval` Python n’est ajouté. Les fichiers d’origine restent en lecture seule ; leur empreinte et leur schéma d’acquisition ne sont jamais remplacés par les colonnes dérivées.

## Expressions

Le parseur produit un arbre contrôlé, puis du SQL paramétré. Les identifiants proviennent du schéma, les fonctions d’un registre explicite. Les valeurs invalides dans les conversions donnent NULL. Les expressions ont des limites de taille/profondeur pour empêcher un fichier de configuration de bloquer l’interface.

Fonctions principales : `Contains`, `StartsWith`, `EndsWith`, `Like`, regex RE2, `Upper`, `Lower`, `Trim`, `Len`, `Substring`, `Replace`, `Insert`, `Remove`, `Concat`, `PadLeft/Right`, `CharIndex`, `Iif`, `IsNull`, `IsNullOrEmpty`, `Coalesce`, conversions de types, calculs, fonctions mathématiques, `GetYear/Month/Day/Hour/Minute/Second`, `AddDays/Months/Years`, `DateDiffDay`, dates relatives et opérateurs logiques/bit à bit. Les noms de colonnes s’écrivent entre crochets. `Line`, `Tag`, `Note` désignent les annotations internes seulement si aucune colonne source ne porte ce nom.

Les collections JSON proposent `Count`, `Exists`, `Sum`, `Avg/Average`, `Min`, `Max` et `Single`, avec sélection d’objets et expressions internes. Exemple : `[Items][[Amount] > 5].Sum([Amount])`. `Single` renvoie NULL sur zéro objet et une erreur sur plusieurs objets. Les fonctions .NET chargées explicitement sont disponibles par nom ou `Custom`, et par les adaptateurs typés `PluginText/Number/Bool/Date`. Les dates CLR conservent leurs ticks de 100 ns et les entiers typés ne transitent pas par un flottant. Une fonction inconnue reste une erreur explicite.

## Dates et profils

Le registre `core/derived.py` compile les colonnes déclaratives dans une vue SQL. Les entiers restent en HUGEINT jusqu’à la conversion finale, sans passer par un flottant. Les résultats UTC conservent neuf décimales ; les tris temporels et filtres de dates conservent aussi les fractions submicrosecondes et tiennent compte du décalage ISO. Les valeurs hors des années 0001–9999 deviennent NULL. Les fractions négatives OLE suivent la convention OLE Automation.

Les fuseaux sont interprétés par ICU embarqué dans DuckDB. Les noms Windows proviennent du mappage global Unicode CLDR (`windows_zones.py`, 142 noms, licence intégrée). Pour les dates sans décalage aux transitions heure d’été/hiver, ICU choisit une interprétation ; cette normalisation ne constitue pas une preuve que l’heure locale était non ambiguë. Conserver les champs sources et utiliser un offset explicite si disponible.

Les traitements de timeline reprennent les catégories et leur ordre de priorité dans TLEFilePlugins `Timelines.cs` à la révision `7199c81`. Plaso/L2T : date + heure + fuseau, indicateurs MACB et catégories. Psort : timestamp et catégories. ForensicTimeline : catégories par artefact. Mactime : dates et catégories par chemin. PeScan/Wisp : assemblage des paires date/heure. Les alias de champs proviennent des métadonnées publiques de 45 profils. Les autres CSV restent lisibles sans exécuter les DLL.

Exemple de profil personnel :

```json
{
  "name": "Export FILETIME",
  "signature": ["Time", "Path"],
  "columns": ["Time", "Path"],
  "transforms": [
    {"name": "TimeUTC", "operation": "timestamp", "columns": ["Time"], "format": "filetime", "timezone": "UTC"},
    {"name": "Extension", "operation": "expression", "expression": "Lower([Path])"}
  ]
}
```

## Migration de layouts

Le lecteur prend en charge les propriétés XML de colonnes et leurs noms de contrôle, ordre, visibilité, largeur, épinglage à gauche ou à droite, tris, groupes et intervalles temporels ; filtres actifs, recherche, résumés, règles de format par expression ou valeur. Les quatre layouts officiels de régression sont conservés sous `tests/fixtures/tle-layouts`, avec provenance et empreintes.

Une colonne absente d’une version d’export est signalée. Une expression qui dépend d’un champ absent ou une règle non traduite arrête l’import au lieu de modifier silencieusement les résultats. Les couleurs ARGB sont composées sur un fond clair et cette adaptation est signalée ; gras, italique, souligné et barré des polices de règles sont repris. Les règles standards à barres, échelles de deux/trois couleurs et jeux de trois à cinq icônes sont traduites, ainsi que les classements, moyennes, doublons et valeurs uniques. Les seuils, leurs comparaisons strictes et le plancher sont conservés. Les formes prédéfinies sont adaptées et signalées ; les images PNG intégrées sont conservées. Les options propres à DevExpress ne deviennent pas automatiquement des préférences Qt.

Les sessions `.tle_sess` reprennent sources et tags, avec détection de BOM UTF-8/16/32 pour les CSV ; les dispositions locales du format sont chargées à l’ouverture des onglets. Le fichier documenté `Settings/TLE_settings.xml` reprend police (y compris les tailles fractionnaires), copie, onglets, détails en haut/bas, formats de dates et épinglage par défaut. Les thèmes DevExpress sont adaptés aux thèmes clair/sombre de Fireblade ; les préférences inconnues sont signalées. Les ouvertures ordinaires et les sessions retrouvent les lecteurs installés dans `Readers` par leurs `ExpectedHeaders`, sans association préalable. Les associations explicites par source restent prioritaires. Sonde bornée à 64 Kio, cache par empreinte de DLL, refus des signatures ambiguës ; aucun lecteur générique sans signature ne remplace l’import natif. Aucun objet .NET sérialisé n’est désérialisé depuis le XML.

## Dépliage et ressources

Le dépliage complet est une vue paginée de tous les groupes et enregistrements. L’index conserve rangs, identifiants et résumés sur disque ; il ne copie pas les cellules forensic volumineuses. Les tris externes et l’indexation utilisent le budget DuckDB et des temporaires. La fenêtre Qt reste bornée à `max_loaded_rows`. Replier rétablit la navigation par branches. L’index est supprimé avec la connexion et reconstruit si la requête change.

Les connexions et checkpoints natifs passent par le worker. Pendant leur attente, la fenêtre continue à traiter les événements Qt ; les commandes de mutation restent désactivées. Cela n’établit pas l’absence de toute pause : les rapports Windows mesurent les intervalles de timer.

Le cache des branches ouvertes manuellement est également borné : les branches les moins récemment chargées peuvent se replier lorsque le budget est atteint, tandis que la branche active et ses ancêtres restent accessibles. Les changements de signets/notes invalident les index de pages triées, y compris lorsque le filtre utilise `Tag`/`Note` ou une colonne dérivée de ces annotations.

Les profils reconnus sont préparés dans le worker d’import avant l’exposition du schéma à la grille ; ils peuvent être désactivés dans les préférences. La conversion temporelle utilise des expressions SQL locales à chaque enregistrement, sans UDF Python ni jointure corrélée sur tous les timestamps distincts. Les colonnes dérivées sont calculées à la demande : un tri/filtre sur une conversion de millions de dates peut donc prendre plusieurs secondes.

La lecture de pages profondes acquiert uniquement les identifiants demandés. Un index natif de ces identifiants est créé à la demande dans l’analyse si le cache est activé, que l’analyse est modifiable et que le budget atteint 128 Mo. Sous un budget réduit, en lecture seule ou après un échec d’allocation de cet index facultatif, la lecture normale reste disponible. Cet index ne modifie pas le CSV.

Les comparaisons et calculs de dates de l’éditeur conservent leur clé UTC en nanosecondes : conditions imbriquées, `Iif`, coalescence, ajouts de jours/mois/années, ticks et fractions de milliseconde. Les conversions de statut de Sigcheck/SigcheckTroy (`Signed`) et Autoruns (`enabled`) suivent les comparaisons exactes des plugins publics dans une colonne booléenne distincte ; le texte source reste disponible.

## Graphiques de cellules

Fireblade propose barres positives/négatives, axe zéro, dégradés à deux/trois couleurs, icônes à trois/cinq niveaux, seuils personnalisés et PNG intégrés. Bornes fixes, minimum/maximum automatiques, pourcent de la plage ou percentiles exacts portent sur tous les résultats filtrés. Les bornes sont mises en cache entre les pages ; un filtre, une annotation ou un rafraîchissement les invalide. Le tri des percentiles utilise une table temporaire à une colonne avec débordement disque, supprimée même après annulation. Les caches de bornes sont limités à 128 entrées.

Classement et moyenne utilisent les nombres normalisés du moteur ; les ex æquo au seuil sont tous retenus. Les doublons sont comparés sur la valeur complète, avec choix de la casse et des NULL. Un préfiltre de fréquences de hachage est toujours suivi d’une vérification exacte pour les candidats ; les collisions ne créent pas de faux doublons. Le cache des valeurs compte environ 8 Mio au maximum. Ces modes statistiques nécessitent un premier parcours global ; une condition ordinaire ne rescane pas les événements.

Chaque règle peut apporter le fond, le texte ou la police ; l’ordre donne la priorité pour chaque propriété. « Arrêter après cette règle » bloque les suivantes. Masquer les valeurs est visuel : copie, détail et export conservent les données. Les bibliothèques JSON restent limitées à 2 Mo, images comprises.


Les règles statistiques et graphiques proposent aussi un calcul sur toute la source, en ignorant le filtre actif. Les moyennes acceptent les comparaisons strictes ou inclusives. Les dates relatives utilisent `InDateRange([Date], 'Today')` et les périodes proposées dans l’éditeur de règles ; les jours sont calculés en UTC, les semaines commencent le lundi. L’import XML reprend les dates relatives combinées, les listes de valeurs et les douze styles texte/fond prédéfinis documentés de DevExpress. Les palettes prédéfinies sont adaptées ; les styles personnalisés inconnus restent refusés.

Références de migration : [types de moyenne](https://docs.devexpress.com/WindowsForms/DevExpress.XtraEditors.FormatConditionRuleAboveBelowAverage.AverageType), [uniques/doublons](https://docs.devexpress.com/WindowsForms/DevExpress.XtraEditors.FormatConditionRuleUniqueDuplicate.FormatType), [styles prédéfinis](https://docs.devexpress.com/WindowsForms/DevExpress.XtraEditors.FormatConditionRuleAppearanceBase.PredefinedName), [dates relatives](https://docs.devexpress.com/WindowsForms/DevExpress.XtraEditors.FormatConditionRuleDateOccuring.DateType).

Les dispositions automatiques sont stockées par identité de lecteur/profil et empreinte du schéma ordonné. Les modifications sont enregistrées à la fermeture ou au changement d’onglet en JSON Fireblade dans `Layouts/Local/*.layout.local` ; ce format reste distinct du XML TLE malgré le suffixe commun. Le lecteur détecte le contenu. Les XML nommés d’après le lecteur/profil, dans les dossiers `Layouts` et `Layouts/Default` utilisateur/portables, sont recherchés après la disposition mémorisée, variantes locales avant défauts. Les snapshots de sessions Fireblade gardent la priorité. Un layout invalide est conservé et signalé, sans empêcher l’import de la source. Aucun rebalayage du CSV n’est requis pour choisir la disposition.

## Tris de résumés et apparences XML

`GroupSummarySortInfoState` est lu comme une suite de données de longueur préfixée en unités UTF-16 : colonne de groupe, direction, référence au résumé par `#index` ou `Tag`. Aucun objet .NET n’est désérialisé. Les références suivent la collection `GroupSummary` originale avant dédoublonnage, comptage intégré compris. Les tags ambigus, références absentes, longueurs invalides et états tronqués sont refusés. Les directions `None` sont inactives.

Chaque niveau conserve ses propres critères ordonnés, puis son ordre de valeur. La pagination, l’index de dépliage et l’export groupé partagent cette définition. Pour l’export, les agrégats sont calculés séparément pour chaque niveau : une moyenne ou un nombre de valeurs distinctes d’un parent n’est pas obtenu en additionnant les valeurs des enfants. Modifier explicitement le tri global ou la liste des résumés dans le dialogue remplace les critères importés ; accepter sans modification les conserve.

Les apparences `Row`, `OddRow`, `EvenRow`, `GroupRow`, `SelectedRow`, `FocusedRow`, `FocusedCell`, `HeaderPanel`, `AppearanceCell` et `AppearanceHeader` deviennent des données de vue validées. Couleurs, polices, alignements, options `UseBackColor/UseForeColor/UseFont/UseTextOptions` et dégradés horizontaux/verticaux/diagonaux sont repris. Les styles conditionnels prédéfinis sont fusionnés avec les propriétés explicites, en respectant les désactivations. Les règles conservent aussi leurs dégradés et alignements après édition et sérialisation. Les en-têtes épinglés utilisent le même rendu que l’en-tête central.

Cela ne reproduit pas tous les dessins DevExpress : les apparences d’autres panneaux, images/bordures et options de texte non représentables restent signalées dans les avertissements de migration. Un nom de style prédéfini inconnu reste refusé. Le choix des icônes et skins exacts reste une adaptation Qt.

Références : [tri des groupes par résumé](https://docs.devexpress.com/WindowsForms/DevExpress.XtraGrid.Views.Grid.GridView.GroupSummarySortInfo), [propriété d’état sérialisé](https://docs.devexpress.com/WindowsForms/DevExpress.XtraGrid.Views.Grid.GridView.GroupSummarySortInfoState), [options d’apparence](https://docs.devexpress.com/WindowsForms/DevExpress.Utils.AppearanceOptions). La structure de l’état a été vérifiée sur les métadonnées de sérialisation fournies avec Timeline Explorer 2026.10.0 ; aucune bibliothèque DevExpress n’est ajoutée à Fireblade. Les tests de nouveaux états sont des fixtures de migration synthétiques ; les quatre XML amont existants continuent à être exécutés.

## Objets complexes transmis aux fonctions .NET

Les arguments provenant de colonnes complexes de lecteurs CLR sont résolus directement dans un contexte .NET partagé par analyse : leurs types, collections, méthodes, état privé et références communes ne sont pas reconstruits depuis JSON. Les membres imbriqués, indices de listes, `Single()` simple et résultats transmis entre fonctions conservent les références natives. Les fonctions de plusieurs DLL compatibles peuvent partager ces objets. La projection JSON reste utilisée pour la grille et les calculs SQL sur collections, sans définir le type des arguments CLR directs.

Le contexte est chargé à la demande, à partir de la source et du lecteur approuvés pour l’analyse ; leurs empreintes et le nombre de lignes sont contrôlés. Le graphe est celui d’une nouvelle exécution du lecteur, conservé jusqu’à fermeture/annulation. Cela exige un lecteur déterministe, une source disponible et des types chargeables dans le même CLR ; aucun transport direct CLR4 ↔ CLR moderne n’est revendiqué. Les retours transitoires ont une limite de 65 536 références en attente et sont nettoyés en fin de requête. Le coût mémoire de `DataList` appartient au lecteur tiers. Voir [les contrats et limites](PLUGINS.md#arguments-clr-natifs).

La qualification ajoute des objets avec état privé, cycles/références partagées, collections génériques, retours imbriqués, deux DLL distinctes, réouverture, colonnes dérivées, source modifiée et annulation. Le helper CLR4 est compilé et son contrôle Windows exige également un argument de classe native.

## Critères avancés, nouveau lot

La grammaire ajoute les champs simples sans crochets, l’échappement `@` des mots réservés, les caractères suffixés `c`, les GUID entre accolades, les suffixes numériques `s/b/f/m/d/L/UL` et les constantes `#!…!#` de date/heure seules. Les GUID ne sont comparables que par égalité/différence. Les limites de types entiers et flottants sont vérifiées. Les `DateOnly`/`TimeOnly` fournis par un lecteur CLR moderne gardent leur représentation ISO et leurs ticks ; les arguments de fonctions .NET conservent aussi les types de constantes déclarés. Le CLR4 ne fournit pas les types `DateOnly`/`TimeOnly` natifs.

Le compilateur de collections distingue les scopes de lambdas. `[Collection][condition]` et `[Collection][]` deviennent des tests d’existence ; `[^.Champ]` et les préfixes successifs `^.^.` accèdent aux parents. Les champs numériques JSON sont comparés numériquement aux parents ; les chaînes JSON restent textuelles. Les dépendances aux colonnes parentes sont incluses dans l’évaluation paginée des couleurs et l’adaptation des règles partagées. La migration XML renomme les alias de colonnes du contexte racine sans renommer les propriétés des objets enfants.

Nouvelles fonctions : `InRange`, `IsNullOrWhiteSpace`, `CharIndex` à trois arguments, `Atn`, `Atn2`, `Sqr`, `Cosh`, `Sinh`, `Tanh`, `Trunc/Truncate`, `Pi`, `Rnd`, `DateTimeFromParts`, `DateOnlyFromParts`, `TimeOnlyFromParts`, `GetTimeOfDay`, `AddTimeSpan`, `IsSameDay`, `IsSameHour`, `IsSameTime`, prédicats de mois, semaines/mois/années/heures relatifs, `IsYearToDate`, variantes `IsOutlookInterval…` couvertes par le registre de périodes, nouvelles bornes `LocalDateTime…` et `InDateRange` à trois arguments. Les différences de ticks/microsecondes comptent les frontières de l’unité, y compris avant 1970. Les durées textuelles conservent sept décimales de seconde. Aucun parcours Python par événement ni UDF supplémentaire n’est nécessaire pour ces calculs SQL.

`parse_filter(text, headers, parameters=[…])` lie des paramètres positionnels en constantes échappées et typées, conservées dans les vues/règles. Les paramètres absents deviennent `Null`. Les chaînes, dates et noms de champs ne sont pas interprétés comme code. Les limites de taille, profondeur et nombre de paramètres restent appliquées. Les conversions invalides donnent NULL ; les références à un parent inexistant sont refusées.

Cela couvre les syntaxes et fonctions identifiées pour les données de grille. Les jointures libres XPO/EF, upcasts de types persistants, énumérations enregistrées dans un registre CLR externe et agrégats personnalisés dépendant d’un fournisseur ne sont pas fabriqués pour un CSV : ils nécessitent le contexte du fournisseur correspondant. Les fonctions non déclarées restent refusées explicitement. Les semaines et fonctions dites locales suivent la convention UTC de Fireblade ; les réglages calendaires/culturels DevExpress ne sont pas reproduits à l’identique. Référence de grammaire et de sémantique : [documentation officielle DevExpress](https://docs.devexpress.com/CoreLibraries/4928/devexpress-data-library/criteria-language-syntax).

La qualification du fichier unique attend désormais l’ouverture effective du dialogue d’import après la détection des lecteurs. Le rapport est enregistré avant/après chaque contrôle ; un dépassement de délai arrête l’arbre du processus onefile, afin de conserver le diagnostic et libérer l’EXE relocalisé.

Les conversions numériques des colonnes réutilisent le chemin natif HUGEINT pour les chaînes entières, sans passer par un flottant ; les autres chaînes conservent le parseur décimal. Un contrôle ciblé sur l’analyse existante du CSV de 3 Go est conservé dans [ce rapport](../validation/reports/advanced-criteria-existing-dataset.json). Il ne constitue pas un benchmark comparatif avec TLE.
