# Écarts de compatibilité à traiter

Référence de travail : Fireblade 0.4 et les usages documentés de Timeline Explorer ; les métadonnées de layouts déjà étudiées dans le projet proviennent de TLE 2026.10.0. Cet inventaire distingue les différences connues et les équivalences non démontrées. Il n'est pas une certification exhaustive de toutes les fonctions de DevExpress, dont certaines ne sont pas exposées dans TLE.

Une ligne est terminée lorsque le comportement est implémenté et vérifié par un cas observable. Une vérification locale Qt sans écran ne constitue pas une qualification native Windows ni un essai humain. L'exécution Actions du commit doit être consultée avant d'annoncer une nouvelle qualification du fichier unique.

## Correctifs implémentés

| ID | Comportement | Preuve ajoutée |
|---|---|---|
| L01 | Import `HighPriority`, fusion par propriété, conservation dans les vues/règles | Tests XML imbriqué/pointé, conflits ligne/colonne/condition/sélection, pixels centraux/épinglés et restauration ; contrôle intégré au fichier unique |
| R01 | Unités indépendantes des seuils d'icônes et du plancher | Import XML, filtrage, percentile exact, cache par modes, priorité en cas de croisement, édition, règles globales, pixels épinglés ; contrôle intégré au fichier unique |
| U01 | Raccourcis TLE pour effacer les filtres, filtrer une cellule et déplier/replier | Envoi des touches Qt, valeur source `001`, NULL, absence de marquage involontaire |
| U02 | Accès aux groupements trimestre/semaine/minute/seconde | Menu d'en-tête et déclenchement d'un regroupement ; ces intervalles existaient dans le moteur |
| L08 | Alpha des couleurs conservé jusqu’au dessin et dans les vues/règles | Pixels clair/sombre, alternance, épinglage, sélection, en-têtes et panneaux ; interpolation alpha et contrôle du fichier unique |
| F02 | Export du contrat `.tle_sess`, sources et signets de tous les onglets | Retour JSON documenté/export/import, correspondance des lecteurs, intégrité, annulation et remplacement atomique ; ouverture dans TLE encore à qualifier (Q07) |

Les contrôles intégrés ajoutés sont `mixed_icon_threshold_units_and_pinned_rendering`, `high_priority_layout_and_selection_rendering` et `argb_layout_pixels_light_dark_and_selection`. Le contrôle existant de sessions vérifie aussi le retour export/import. Les nouveaux exemples XML sont synthétiques. Ils complètent les quatre layouts amont conservés dans `tests/fixtures/tle-layouts` ; ils ne prouvent pas à eux seuls une identité de toutes les variantes TLE.

## Différences encore connues

| ID | Écart | Condition de clôture |
|---|---|---|
| L02 | `FooterPanel` et `GroupFooter` partagent un contrôle | Pied global et pieds de groupes distincts avec résumés et styles indépendants ; navigation, export, pagination et colonnes épinglées vérifiés |
| L03 | Hauteur de renvoi à la ligne bornée à trois lignes | Définir et comparer les options de hauteur réellement exposées par TLE ; reproduire le comportement sans mesure globale des millions de cellules |
| L04 | Skins, métriques et dessins adaptés à Qt | Comparaison visuelle Windows des réglages exposés dans TLE ; distinguer équivalence d'usage et identité graphique |
| L05 | Propriétés/rôles/variantes XML hors des traductions explicites | Inventorier des layouts TLE réellement produits, associer chaque propriété active à un résultat attendu et à un test |
| L06 | Styles nommés sans définition embarquée | Importer une définition exportable lorsqu'elle existe ; signaler les définitions externes absentes sans inventer leur contenu |
| L07 | Images raster bornées, enveloppes bitmap partielles, chemins externes refusés | Identifier les formats effectivement produits par TLE ; ajouter des décodeurs de données vérifiables si nécessaires, sans désérialisation exécutable |
| R02 | Pictogrammes et palettes prédéfinis adaptés ; variantes hors du lecteur refusées | Comparer les jeux et options réellement disponibles dans TLE, avec seuils limites, ordre et rendu |
| P01 | `FirstPinnedColumns` structuré non traduit | Obtenir un exemple TLE réel et vérifier son import et l'application par format |
| P02 | Champs supplémentaires des préférences non traduits | Comparer les préférences exportées par la version cible de TLE et tester chaque champ actif |
| F01 | Pas d'export XML DevExpress des dispositions Fireblade | Produire un XML accepté par TLE et vérifier le parcours Fireblade → TLE → Fireblade, sans prétendre exporter les options propres à Fireblade |
| E01 | Conventions UTC/calendaires/culturelles différentes | Jeux comparatifs TLE/Fireblade pour périodes relatives, cultures, fuseaux et transitions heure d'été/hiver |
| E02 | Expressions dépendant d'un fournisseur externe | Confirmer d'abord leur utilisation réelle dans TLE ; fournir le contexte requis ou conserver une erreur explicite |
| D01 | Catalogue de reconnaissance différent d'une qualification complète des lecteurs | Jeux d'entrée/sortie de référence par lecteur et version, comparés à TLE |
| D02 | Variantes de supertimelines non toutes qualifiées | Comparer dates, MACB, catégories, couleurs et champs dérivés pour chaque variante ciblée |
| D03 | DLL/dépendances/contrats tiers non tous qualifiés | Matrice de lecteurs et fonctions réels, sur CLR4 et CLR moderne compatibles |
| D04 | Objets CLR reconstruits depuis source et lecteur déterministe | Définir les garanties de persistance et comparer les cas source absente/modifiée et lecteurs non déterministes |
| D05 | Détection de lecteur limitée à 64 Kio d'en-tête | Comparer un en-tête dépassant cette limite avec TLE et décider d'une sonde progressive bornée si nécessaire |
| N01 | Navigation par fenêtres et indexation initiale du dépliage | Comparer les gestes, accès profonds, sélection et réactivité avec TLE sur les mêmes données |

Les plafonds de Fireblade (règles, résumés, sessions, tags, tailles de fichiers de configuration) sont documentés mais leur caractère plus restrictif que TLE n'est pas établi pour chaque cas. Ils demandent une comparaison avant d'être tous traités comme des fonctions manquantes.

## Qualifications encore à réaliser

| ID | Preuve manquante |
|---|---|
| Q01 | Comparaison fonctionnelle et visuelle avec TLE sur un même poste Windows et une version identifiée |
| Q02 | Plus de 300 fichiers ouverts et recherche/navigation entre eux |
| Q03 | Fichier de plus de 14 Go, valeur mentionnée par le manuel TLE ; réutiliser des données existantes, ne jamais régénérer le CSV de 3 GiB |
| Q04 | Benchmark comparatif mémoire, import, filtres, tris, regroupements et réactivité |
| Q05 | Sessions prolongées sur vrais exports, gestes de l'Explorateur, dialogues natifs et diversité des partages Windows |
| Q06 | Correspondance complète des priorités d'apparence avec des layouts exportés par TLE, au-delà des cas synthétiques |
| Q07 | Ouverture dans TLE de sessions exportées, avec lecteurs réels et tags ; les tests actuels valident le contrat documenté et le retour dans Fireblade |

La signature de code reste écartée conformément à la demande de l'utilisateur. PDF/HTML, tags catégorisés, reprise d'import après panne et paquet autonome d'enquête ne sont pas listés comme manques face à TLE tant que leur présence dans TLE n'est pas établie.
