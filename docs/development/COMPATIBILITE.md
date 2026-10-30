# Compatibilité et transformations

Le moteur est Python + DuckDB + Qt. Aucun moteur .NET, serveur, langage de script de plugin ou `eval` n’est ajouté. Les fichiers d’origine restent en lecture seule ; leur empreinte et leur schéma d’acquisition ne sont jamais remplacés par les colonnes dérivées.

## Expressions

Le parseur produit un arbre contrôlé, puis du SQL paramétré. Les identifiants proviennent du schéma, les fonctions d’un registre explicite. Les valeurs invalides dans les conversions donnent NULL. Les expressions ont des limites de taille/profondeur pour empêcher un fichier de configuration de bloquer l’interface.

Fonctions principales : `Contains`, `StartsWith`, `EndsWith`, `Like`, regex RE2, `Upper`, `Lower`, `Trim`, `Len`, `Substring`, `Replace`, `Insert`, `Remove`, `Concat`, `PadLeft/Right`, `CharIndex`, `Iif`, `IsNull`, `IsNullOrEmpty`, `Coalesce`, conversions de types, calculs, fonctions mathématiques, `GetYear/Month/Day/Hour/Minute/Second`, `AddDays/Months/Years`, `DateDiffDay`, dates relatives et opérateurs logiques/bit à bit. Les noms de colonnes s’écrivent entre crochets. `Line`, `Tag`, `Note` désignent les annotations internes seulement si aucune colonne source ne porte ce nom.

Ce registre ne prétend pas exécuter les fonctions .NET personnalisées ni les agrégats d’objets enfants de DevExpress. Une fonction non reconnue provoque une erreur explicite.

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

Une colonne absente d’une version d’export est signalée. Une expression qui dépend d’un champ absent ou une règle non traduite arrête l’import au lieu de modifier silencieusement les résultats. Les couleurs ARGB sont composées sur un fond clair et cette adaptation est signalée ; seul le gras des polices de règles est repris. Les règles à barres, échelles de couleurs et jeux d’icônes ne sont pas traduites. Les options propres à DevExpress ne deviennent pas automatiquement des préférences Qt.

Les sessions `.tle_sess` reprennent sources et tags ; les layouts restent des fichiers séparés à importer sur l’analyse correspondante. Les paramètres propriétaires de l’application et plugins binaires ne sont pas désérialisés.

## Dépliage et ressources

Le dépliage complet est une vue paginée de tous les groupes et enregistrements. L’index conserve rangs, identifiants et résumés sur disque ; il ne copie pas les cellules forensic volumineuses. Les tris externes et l’indexation utilisent le budget DuckDB et des temporaires. La fenêtre Qt reste bornée à `max_loaded_rows`. Replier rétablit la navigation par branches. L’index est supprimé avec la connexion et reconstruit si la requête change.

Les connexions et checkpoints natifs passent par le worker. Pendant leur attente, la fenêtre continue à traiter les événements Qt ; les commandes de mutation restent désactivées. Cela n’établit pas l’absence de toute pause : les rapports Windows mesurent les intervalles de timer.
