# Espace de travail — Fireblade 0.2.2

## Artefacts et recherche

Dans **Analyses**, l’arbre **Artefacts** organise les résultats par famille. Le sélecteur au-dessus de l’arbre propose aussi les dossiers sources ou une liste simple. Le champ de l’arbre filtre les noms ; le champ principal cherche les valeurs dans **tous les artefacts ouverts** par défaut. Choisissez **Artefact actif** pour limiter la recherche.

Validez avec Entrée. Les résultats apparaissent dans un panneau redimensionnable : nombre de correspondances par artefact, erreurs éventuelles et accès par double-clic à l’analyse filtrée. Les artefacts sans correspondance sont masqués par défaut. Les bases inactives sont ouvertes successivement, sans charger toutes les données en RAM.

Un clic droit sur une cellule propose **Rechercher dans tous les artefacts** et **Corréler dans toutes les analyses**. Les occurrences sont surlignées dans le texte ; les signets et les règles de coloration conservent leur propre présentation.

## Réorganiser l’écran

Le bouton **Espace de travail** propose **Analyse**, **Chronologie seule** et **Analyse + chronologie**. Ce dernier affiche le graphique à côté de la grille. **Chronologie seule** masque les autres commandes et donne la place à la chronologie ; le menu Espace de travail reste accessible pour revenir.

Un clic droit sur l’onglet d’un panneau permet de le détacher. Glissez sa barre de titre pour le déplacer, l’ancrer ou en faire une fenêtre séparée. Redimensionnez les séparateurs à la souris. Le menu permet également de détacher l’arbre des artefacts et les détails de ligne. Pour rattacher ces deux panneaux, utilisez le clic droit sur leur barre de titre.

**Enregistrer la disposition** mémorise positions, dimensions, séparateurs et colonnes de chronologie. La disposition est également enregistrée à la fermeture. **Rétablir les panneaux** permet de retrouver l’espace d’analyse.

## Colonnes par artefact

Glissez les en-têtes de la grille pour choisir leur ordre. Le menu **Affichage → Colonnes et tri → Colonnes…** propose aussi une liste réorganisable par glisser-déposer, avec cases de visibilité. Les colonnes épinglées peuvent être réordonnées dans leur zone.

L’ordre et les largeurs sont enregistrés automatiquement après une courte pause et retrouvés pour les prochains fichiers du même format. Les schémas différents restent indépendants. Les vues enregistrées et sessions conservent leur propre disposition.

## Chronologie

L’ouverture de la chronologie construit l’index si nécessaire. **Sources et dates…** permet de vérifier quelle colonne représente l’événement. **Événements** masque ou affiche la liste ; **Détails** contrôle l’inspecteur. Le graphique peut ainsi occuper toute la hauteur. Les pistes et la densité d’activité donnent une vue commune des artefacts ; glissez sur le graphique pour isoler une période, utilisez la molette pour zoomer ou choisissez une durée rapide. **Dates…** ouvre la sélection précise et **Vue globale** réinitialise la période. Le double-clic sur un événement retrouve la ligne source.

Les dates sans fuseau et les lignes sans date sont identifiées séparément. Une date interprétée n’est pas une preuve d’attribution : vérifiez toujours la source et le fuseau horaire.

## Ressources, règles et plugins

**Affichage → Préférences… → Ressources** enregistre la mémoire par analyse, les threads de requête/recherche et ceux d’import/parsing. Les tâches déjà lancées gardent leurs réglages ; les collectes sont séquentielles. Les moteurs externes conservent leurs propres options de parallélisme. Les exports conservent leurs parcours à mémoire bornée.

**Règles** ouvre l’éditeur de coloration existant : conditions ET/OU/NON, colonnes ciblées et règles statistiques. Les recherches et règles n’altèrent pas les valeurs sources.

**Plugins** permet d’installer un profil JSON ou de créer un profil depuis les colonnes de l’artefact courant. Le JSON est validé avant enregistrement. Un profil décrit reconnaissance, types, ordre et transformations ; ce n’est pas un parser. Pour un lecteur personnalisé, utilisez **Préférences → Plugins → Lecteurs .NET…**. Les contrats .NET et exemples restent décrits dans la documentation de développement.
