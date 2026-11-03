# Apparences des layouts Timeline Explorer

Fireblade importe les données XML de disposition sans installer DevExpress. Importez un `.layout`/`.layout.local` depuis le menu Fichier, ou utilisez le chargement automatique par format décrit dans le README. Les propriétés explicites complètent les styles prédéfinis et les options `Use…` peuvent les désactiver. Les vues Fireblade et les dispositions locales mémorisées conservent les valeurs importées.

## Éléments dessinés

| Apparence TLE | Présentation Fireblade |
|---|---|
| `Row`, `OddRow`, `EvenRow`, `GroupRow` | Lignes ordinaires, alternées et groupes |
| `AppearanceCell`, `AppearanceHeader` | Cellule/en-tête de la colonne correspondante |
| `HeaderPanel` | En-têtes centraux et épinglés à gauche/droite |
| `SelectedRow`, `FocusedRow`, `FocusedCell` | Sélection et focus |
| `GroupPanel` | Barre de groupement, avec glisser-déposer conservé |
| `FooterPanel` | Pied global : comptage et résumés globaux du résultat filtré |
| `GroupFooter` | Lignes de pied de chaque groupe, avec style et valeurs indépendants |
| `ViewCaption` | Libellé du fichier dans la barre d’état |
| `Preview` | Panneau de détails de la ligne sélectionnée |
| `FilterPanel`, `FindPanel` | Liste des filtres et champ de recherche |
| `Empty` | Fond de la grille sans résultat |

Les couleurs, dégradés, polices, attributs de police et alignements restent pris en charge. `BorderColor` dessine une bordure ; `UseBorderColor=false` la désactive. Les styles portables peuvent aussi définir sa largeur (1 à 8 pixels) et son trait (`Solid`, `Dash`, `Dot`). Les règles conditionnelles reprennent ces propriétés supplémentaires lorsqu’elles correspondent à une cellule.

## Images

`Image`, ou `ImageOptions.Image`, accepte une image PNG/JPEG/BMP/GIF encodée en base64, éventuellement sous forme `data:image/…;base64,…`. Les enveloppes binaires courantes de `System.Drawing.Bitmap` contenant un PNG/JPEG peuvent être extraites sans désérialiser d’objet .NET. Un autre format est refusé explicitement. Les chemins de fichiers externes et les objets exécutables ne sont pas chargés.

Chaque image est limitée à **256 Kio et 1024 × 1024 pixels**. Les décodages sont partagés par les cellules, avec huit images décodées au maximum dans le cache. `ImageAlignment` reprend les neuf positions `TopLeft` à `BottomRight`, avec `MiddleCenter` au centre. Une image trop grande pour une cellule est réduite en conservant ses proportions. Les contrôles de recherche/filtres utilisent leur moteur Qt natif ; les images de ces contrôles gardent leur taille et sont coupées aux limites du panneau. Le panneau de détails dessine l’image derrière son texte. Les images nécessaires aux feuilles de style des contrôles natifs passent par un répertoire temporaire supprimé à la fermeture normale ; aucun fichier compagnon à distribuer avec l’EXE n’est nécessaire.

## Texte

Dans les cellules et en-têtes :

- `WordWrap=Wrap/NoWrap` active ou désactive le renvoi à la ligne. Avec `OptionsView.RowAutoHeight=true`, la hauteur s’adapte au texte affiché des seules lignes chargées, y compris ses sauts de ligne. Les volets centraux et épinglés partagent le même calcul et défilent en pixels. Sans hauteur automatique, le mode uniforme conserve la réserve de trois lignes pour `Wrap`.
- `Trimming=None/Character/Word/EllipsisCharacter/EllipsisWord/EllipsisPath` choisit la coupure ou les points de suspension, au milieu pour un chemin. Le dessin est adapté aux métriques Qt ; le texte complet reste disponible dans les détails et à l’export.
- `HotkeyPrefix=None/Show/Hide` traite les préfixes `&` comme du texte ordinaire, un raccourci souligné ou un raccourci masqué.
- `UseTextOptions=false` retire les options héritées du style prédéfini.

Les champs de saisie, filtres et détails conservent leurs interactions natives. Les alignements de saisie et le renvoi à la ligne des filtres/détails sont adaptés aux possibilités de ces contrôles ; la troncature et les préfixes clavier de la grille ne réécrivent pas leur contenu.

## Styles prédéfinis personnalisés

Les douze styles texte/fond standards restent disponibles. Un `PredefinedName` personnalisé doit disposer d’une définition : son nom seul dans un XML ne permet pas de retrouver une couleur définie dans le code d’une application tierce.

Ajoutez un fichier JSON UTF-8 :

- `%LOCALAPPDATA%\Fireblade\Layouts\styles.json` pour une bibliothèque commune ;
- `<chemin-complet-du-layout>.styles.json` pour une bibliothèque associée, par exemple `EvtxECmd.layout.styles.json`.

La bibliothèque associée remplace les définitions communes de même nom. Une définition personnalisée peut aussi remplacer un style standard. Exemple :

```json
{
  "Evidence": {
    "background": "#fff2cc",
    "foreground": "#7f6000",
    "bold": true,
    "border_color": "#bf9000",
    "border_width": 2,
    "border_style": "Solid",
    "word_wrap": true,
    "trimming": "EllipsisWord"
  }
}
```

Les clés de présentation supplémentaires sont `background2`, `gradient` (`Horizontal`, `Vertical`, `ForwardDiagonal`, `BackwardDiagonal`), `italic`, `underline`, `strikeout`, `font_family`, `font_size`, `horizontal` (`Near`, `Center`, `Far`, `Default`), `vertical` (`Top`, `Center`, `Bottom`, `Default`), `hotkey`, `image` (base64 raster) et `image_align`. Les couleurs utilisent `#RRGGBB` ou `#AARRGGBB` pour conserver une transparence. Une bibliothèque est limitée à 1 Mio et 128 noms ; les propriétés inconnues sont refusées.

Après import et sauvegarde d’une vue Fireblade, les propriétés résolues sont intégrées au fichier : la bibliothèque n’est plus nécessaire pour rouvrir cette vue. Pour réimporter le XML d’origine avec son nom personnalisé, conservez la bibliothèque. Un style sans définition produit une erreur explicite.

## Vérifications et limites

Les tests d’interface chargent des XML, vérifient les pixels des images/bordures/fonds, la hauteur des lignes et en-têtes épinglés, les règles conditionnelles, la sauvegarde/réouverture et le retrait des styles lorsqu’on change de vue. Ils contrôlent également les données d’image invalides et les options désactivées.

Le rendu est une adaptation Qt : les skins, métriques exactes, dessins propriétaires et propriétés XML non reconnues ne sont pas reproduits à l’identique. Les propriétés d’apparence actives non reprises sont signalées lors de l’import. Les autres variantes XML restent suivies dans l’inventaire de compatibilité. La taille maximale d’un layout demeure 4 Mio. Les tests d’apparence ne constituent pas un nouveau benchmark du CSV de 3 Gio ; ce fichier existant n’est pas régénéré pour ces changements.


## Priorités d’apparence

`Options.HighPriority` est lu dans les deux formes XML : option imbriquée dans `Options` ou propriété nommée `Options.HighPriority`. La valeur doit être `true` ou `false`. Elle est conservée dans les vues et les styles conditionnels.

La fusion se fait par propriété : les apparences prioritaires passent après les apparences ordinaires. Entre deux apparences de même priorité, la plus spécifique ou la dernière couche applicable prévaut : ligne, alternance, colonne, règles conditionnelles dans leur ordre de priorité, sélection, ligne active et cellule active. Une ligne prioritaire ne définissant que le fond ne remplace donc pas une couleur de texte fournie par une autre règle. Une option `Use…=false` ne fournit aucune valeur pour la propriété désactivée. Les en-têtes centraux et épinglés appliquent la même fusion.

Les tests vérifient les conflits ligne/colonne/règle/sélection, les pixels dessinés, les en-têtes épinglés, la sauvegarde et le retour au style ordinaire. Le parcours Windows du fichier unique contient ces contrôles. Cela ne garantit pas l’identité de toutes les variantes de rendu DevExpress.

## Types de seuils d’icônes indépendants

Une règle peut combiner des seuils numériques, en pourcentage de la plage et en percentile. Chaque seuil et le plancher gardent leur propre type. Le menu des règles propose un type commun et une dérogation pour chaque seuil. L’import conserve l’ordre de priorité des icônes XML ; il ne trie pas ensemble des nombres exprimés dans des unités différentes.

Les pourcentages et percentiles sont calculés sur l’ensemble des résultats filtrés, ou sur toute la source lorsque cette option est activée. Si des seuils de types différents se croisent après filtrage, l’icône de priorité la plus élevée dont le seuil est satisfait est retenue. Les comparaisons `>`/`>=` et les types du plancher restent conservés. Les anciens fichiers avec un type commun restent lisibles.


## Transparence des couleurs

Les couleurs XML `A, R, G, B` et les couleurs `#AARRGGBB` conservent leur alpha dans les cellules, règles, dégradés, bordures, en-têtes et panneaux. Elles sont composées au dessin sur le fond effectif, y compris les lignes alternées du thème sombre. Les échelles de couleurs interpolent aussi l’alpha. Le choix de couleur des règles propose un canal alpha et l’édition/sauvegarde conserve les valeurs importées.

Le texte automatique tient compte du fond composé lorsqu’aucune couleur de texte explicite n’est imposée. Les tests vérifient les pixels des thèmes clair/sombre, les colonnes épinglées, la sélection et les panneaux ; un parcours équivalent est ajouté à la qualification du fichier unique. Cela ne constitue pas une comparaison visuelle exhaustive avec chaque skin TLE.


## Pieds de groupes et pied global

`GroupSummary` et `TotalSummary` alimentent deux listes distinctes. Les résumés globaux des colonnes sérialisés dans `SummaryItem` ou `Summary` sont aussi repris. Les agrégats globaux portent directement sur les enregistrements filtrés, indépendamment du groupement et de la page visible : une moyenne globale ne résulte pas de la moyenne des moyennes de groupes.

`OptionsView.GroupFooterShowMode` reprend `Hidden`, `VisibleIfExpanded` et `VisibleAlways`. Dans le second mode, le pied suit la dernière page du groupe déplié. Dans le troisième, il suit le sous-arbre du groupe et reste présent lorsque ce groupe est replié. Le dépliage complet stocke aussi les positions des pieds dans son index sur disque. Ces lignes de présentation ne sont ni des événements sélectionnables, ni des signets, et ne sont jamais ajoutées aux exports des données source.

`ShowInGroupColumnFooterName` associe un résumé à une colonne de pied, y compris par son nom de contrôle TLE. Sans cette association, le résumé importé reste dans l’en-tête de groupe. **Affichage → Résumés et tri des groupes** permet de choisir l’emplacement des résumés, le mode des pieds et les agrégats globaux. Modifier seulement leur présentation conserve les critères de tri importés. `OptionsView.ShowFooter` commande l’affichage des résumés globaux ; le compteur de navigation Fireblade reste disponible.

`GroupFooter` possède son propre fond, texte, police, images et bordures. `FooterPanel` s’applique au pied global. Les valeurs et styles restent conservés dans les vues et sessions.

## Hauteurs et texte affiché

`RowHeight`, `GroupRowHeight` et `ColumnPanelRowHeight` sont importés ; `-1` conserve la hauteur par défaut. Les hauteurs explicites acceptent 1 à 10 000 pixels logiques. En mode automatique, les hauteurs de lignes servent de minimum et le texte peut les augmenter. **Affichage → Hauteur des lignes** propose les mêmes réglages et le renvoi à la ligne par défaut.

Le calcul utilise les largeurs réelles des colonnes visibles, y compris celles épinglées, et les polices des cellules. Chaque nœud de la fenêtre chargée conserve un résultat de hauteur ; un redimensionnement, un changement de police ou de vue l’invalide. Aucun parcours du CSV ou requête SQL n’est lancé pendant ce calcul. Le texte de grille reste borné à 600 caractères par cellule ; les détails, la copie et l’export conservent les valeurs complètes. Cette limite d’affichage et les métriques Qt restent distinctes d’une équivalence visuelle exhaustive avec TLE.

## Export XML vers Timeline Explorer

**Analyse → Exporter la disposition → Disposition Timeline Explorer (*.layout)** écrit un XML `XtraSerializer` déclaratif. L’export reprend ordre, largeur et visibilité des colonnes, épinglage gauche/droite, filtres, recherche, groupes et intervalles, tri, résumés et pieds, hauteurs, apparences et règles conditionnelles/graphiques/statistiques. Les largeurs masquées sont conservées, ainsi que les largeurs publiques TLE dépassant 10 000 pixels, jusqu’à la borne Qt de 1 048 575 pixels.

Les noms de contrôles et champs TLE importés restent dans la vue et sont réutilisés à l’export. Les expressions TLE d’origine sont conservées avec une empreinte du filtre traduit : une expression de collection inchangée retrouve sa syntaxe TLE ; une modification ne peut pas réutiliser un ancien filtre. Une expression propre à Fireblade sans traduction vérifiée, un filtre de signets dépendant de tags non exportés ou une population statistique sans équivalent est refusé avant remplacement du fichier. Les options de présentation propres à Fireblade non exportées sont signalées. Une police partielle sans famille/taille explicites est complétée par Segoe UI et 9 pt pour les valeurs manquantes, avec avertissement ; le format natif conserve l’héritage exact. Le type numérique des tris et résumés doit être fourni par le lecteur TLE, une propriété XML de présentation ne modifiant pas son type CLR. Le format `.fireblade-view` conserve l’ensemble des options Fireblade.

L’écriture est atomique et passe par la protection commune des sources/analyses dans l’interface. Les tests couvrent les 190 layouts par défaut du dépôt public de plugins épinglé, avec des schémas déduits des XML : c’est une preuve de lecture/écriture du contrat, pas une exécution des lecteurs ni une preuve que chaque version de l’application TLE acceptera le résultat. L’ouverture dans une version identifiée de TLE demeure une qualification distincte.

## Préférences d’épinglage par lecteur

L’import de `FirstPinnedColumns` accepte la liste de noms documentée et les dictionnaires DataContract dont chaque entrée contient `Key` et `Value` (une liste de `string`). Les clés sont associées au nom complet du lecteur, puis au nom court, puis au profil reconnu ; les valeurs génériques `GenericCsv` s’appliquent aux CSV non reconnus. Les choix par lecteur prennent priorité sur la liste générale et restent dans les préférences sauvegardées. Une forme inconnue ou des clés ambiguës préservent les réglages actuels avec un avertissement. La forme dictionnaire est testée sur des exemples synthétiques ; l’exemple public des préférences TLE contient une collection vide.

Les enveloppes d’images .NET contenant un PNG, JPEG, BMP ou GIF décodable sont lues uniquement comme des pixels bornés, puis normalisées en PNG. Aucun type .NET n’est désérialisé et aucun chemin n’est suivi. Le décodeur GIF reste dépendant des formats Qt disponibles ; les formats sans décodeur sont refusés explicitement.
