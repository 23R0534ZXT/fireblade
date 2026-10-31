# Compatibilité et transformations

Le moteur est Python + DuckDB + Qt. Un hôte .NET autonome, lancé uniquement sur demande, permet l’utilisation explicite de lecteurs et de fonctions TLE. Aucun serveur ni `eval` Python n’est ajouté. Les fichiers d’origine restent en lecture seule ; leur empreinte et leur schéma d’acquisition ne sont jamais remplacés par les colonnes dérivées.

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

Le lecteur prend en charge les propriétés XML de colonnes et leurs noms de contrôle, ordre, visibilité, largeur, épinglage à gauche, tris, groupes et intervalles temporels ; filtres actifs, recherche, résumés, règles de format par expression ou valeur. Les quatre layouts officiels de régression sont conservés sous `tests/fixtures/tle-layouts`, avec provenance et empreintes.

Une colonne absente d’une version d’export est signalée. Une expression qui dépend d’un champ absent ou une règle non traduite arrête l’import au lieu de modifier silencieusement les résultats. Les couleurs ARGB sont composées sur un fond clair et cette adaptation est signalée ; gras, italique, souligné et barré des polices de règles sont repris. Les règles standards à barres, échelles de deux/trois couleurs et jeux de trois à cinq icônes sont traduites, ainsi que les classements, moyennes, doublons et valeurs uniques. Les seuils, leurs comparaisons strictes et le plancher sont conservés. Les formes prédéfinies sont adaptées et signalées ; les images PNG intégrées sont conservées. Les options propres à DevExpress ne deviennent pas automatiquement des préférences Qt.

Les sessions `.tle_sess` reprennent sources et tags, avec détection de BOM UTF-8/16/32 pour les CSV ; les layouts restent des fichiers séparés à importer sur l’analyse correspondante. Le fichier documenté `Settings/TLE_settings.xml` reprend police (y compris les tailles fractionnaires), copie, onglets, détails en haut/bas, formats de dates et épinglage par défaut. Les thèmes DevExpress sont adaptés aux thèmes clair/sombre de Fireblade ; les préférences inconnues sont signalées. Les sessions réimportent les sources avec les lecteurs natifs ; un lecteur DLL particulier se sélectionne séparément. Aucun objet .NET sérialisé n’est désérialisé depuis le XML.

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
