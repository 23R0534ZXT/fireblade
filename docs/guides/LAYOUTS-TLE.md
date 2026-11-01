# Apparences des layouts Timeline Explorer

Fireblade 0.4 importe les données XML de disposition sans installer DevExpress. Importez un `.layout`/`.layout.local` depuis le menu Fichier, ou utilisez le chargement automatique par format décrit dans le README. Les propriétés explicites complètent les styles prédéfinis et les options `Use…` peuvent les désactiver. Les vues Fireblade et les dispositions locales mémorisées conservent les valeurs importées.

## Éléments dessinés

| Apparence TLE | Présentation Fireblade |
|---|---|
| `Row`, `OddRow`, `EvenRow`, `GroupRow` | Lignes ordinaires, alternées et groupes |
| `AppearanceCell`, `AppearanceHeader` | Cellule/en-tête de la colonne correspondante |
| `HeaderPanel` | En-têtes centraux et épinglés à gauche/droite |
| `SelectedRow`, `FocusedRow`, `FocusedCell` | Sélection et focus |
| `GroupPanel` | Barre de groupement, avec glisser-déposer conservé |
| `FooterPanel`, `GroupFooter` | Panneau de comptage ; ces deux apparences partagent le même contrôle, la dernière définition XML prévaut |
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

- `WordWrap=Wrap/NoWrap` active ou désactive le renvoi à la ligne. La hauteur uniforme réserve trois lignes lorsqu’un style utilise `Wrap`, puis coupe le débordement. Ce choix garde les colonnes épinglées alignées et évite de mesurer chaque ligne d’un gros CSV.
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

Les clés de présentation supplémentaires sont `background2`, `gradient` (`Horizontal`, `Vertical`, `ForwardDiagonal`, `BackwardDiagonal`), `italic`, `underline`, `strikeout`, `font_family`, `font_size`, `horizontal` (`Near`, `Center`, `Far`, `Default`), `vertical` (`Top`, `Center`, `Bottom`, `Default`), `hotkey`, `image` (base64 raster) et `image_align`. Les couleurs utilisent `#RRGGBB`. Une bibliothèque est limitée à 1 Mio et 128 noms ; les propriétés inconnues sont refusées.

Après import et sauvegarde d’une vue Fireblade, les propriétés résolues sont intégrées au fichier : la bibliothèque n’est plus nécessaire pour rouvrir cette vue. Pour réimporter le XML d’origine avec son nom personnalisé, conservez la bibliothèque. Un style sans définition produit une erreur explicite.

## Vérifications et limites

Les tests d’interface chargent des XML, vérifient les pixels des images/bordures/fonds, la hauteur des lignes et en-têtes épinglés, les règles conditionnelles, la sauvegarde/réouverture et le retrait des styles lorsqu’on change de vue. Ils contrôlent également les données d’image invalides et les options désactivées.

Le rendu est une adaptation Qt : les skins, métriques exactes, dessins propriétaires, `HighPriority` et propriétés XML non reconnues ne sont pas reproduits à l’identique. Les propriétés actives non reprises sont signalées lors de l’import. La taille maximale d’un layout demeure 4 Mio. Les tests d’apparence ne constituent pas un nouveau benchmark du CSV de 3 Gio ; ce fichier existant n’est pas régénéré pour ces changements.
