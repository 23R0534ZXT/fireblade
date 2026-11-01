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

Les contrôles intégrés ajoutés sont `mixed_icon_threshold_units_and_pinned_rendering`, `high_priority_layout_and_selection_rendering` et `argb_layout_pixels_light_dark_and_selection`. Le contrôle existant de sessions vérifie aussi le retour export/import. Les contrôles suivants portent sur les pieds séparés, les hauteurs automatiques et la sonde progressive. Les nouveaux exemples XML sont synthétiques. Ils complètent les quatre layouts amont conservés dans `tests/fixtures/tle-layouts` ; ils ne prouvent pas à eux seuls une identité de toutes les variantes TLE.

Les développements suivants complètent ce suivi :

| ID | Comportement implémenté | Preuves et portée |
|---|---|---|
| L02 | Pieds de groupes et pied global séparés, agrégats distincts, colonnes et modes de visibilité | Ordre des pieds, fenêtres, repli/dépliage, pixels, épinglage, export source sans faux événements, sauvegarde et calculs globaux directs ; test disque sous 64 Mio avec pieds |
| L03 | `RowAutoHeight`, hauteurs explicites et réglage depuis l’interface | Plus de trois lignes, retour à la hauteur uniforme, redimensionnement sans SQL, cache des nœuds chargés et défilement synchronisé ; texte affiché toujours limité à 600 caractères et comparaison visuelle TLE encore en Q06 |
| D05 | Sonde d’en-tête progressive au-delà de 64 Kio | UTF-8/16/32, champs multilignes, guillemets, EOF sans fin de ligne, préfixe tronqué refusé ; une lecture pour les petits en-têtes, borne totale de 4 Mio |

Les onglets multilignes sont limités à trois rangées visibles, avec défilement vertical vers toutes les analyses et maintien de l’onglet actif dans la zone visible. Un test couvre aussi un clic pendant une reconstruction différée et une boucle d’événements imbriquée : le widget cliqué reste vivant jusqu’à la fin du geste.

## Lot de correction consolidé

| ID | Correction et preuve disponible | Limite de la preuve |
|---|---|---|
| F01 | Export XML `XtraSerializer` depuis le menu, colonnes/épinglage/filtres/groupes/résumés/apparences/règles, écriture atomique et protection des sources | Retour Fireblade et contrat XML vérifiés ; acceptation par une application TLE identifiée encore en Q08 |
| L05 | Corpus des 190 layouts publics épinglés, import et retour XML ; correction des cinq layouts rejetés pour largeur supérieure à 10 000 px | Schémas déduits des XML : aucune prétention à qualifier tous les lecteurs ou toutes les variantes DevExpress |
| P01 | Dictionnaires `Key`/`Value` de noms de colonnes par lecteur, priorité et persistance, structure inconnue conservée avec avertissement | Exemples de dictionnaires synthétiques ; l’exemple public TLE est vide |
| L07 | Enveloppes raster PNG/JPEG/BMP/GIF normalisées sans désérialisation d’objet ni lecture de chemin | Formats disponibles du décodeur Qt et limites d’images documentées ; variantes non observées non revendiquées |
| D04 | Empreinte de la projection publique convertie ; reconstruction refusée si les valeurs changent à source/DLL/comptage identiques | Ne sérialise pas un état privé arbitraire ; les anciens imports sans cette empreinte gardent les vérifications précédentes |
| N01 | Pages profondes non triées servies par un ordre d’identifiants sur disque et des acquisitions bornées ; filtres et invalidation vérifiés | Comparaison des gestes/réactivité avec TLE toujours en Q01/Q04 |
| D01/D03 | Matrice amont : 227 tests réussis, puis 207 variantes synthétiques et 178 lecteurs importés par le helper .NET sous Linux | Qualification native Windows distincte dans la CI ; les entrées synthétiques ne remplacent pas des exports réels ni des DLL propriétaires |
| Q02 | Parcours de 320 analyses : imports, clics premier/milieu/dernier, recherche globale, sauvegarde et restauration ; réussi sous Qt hors écran | Le même parcours du véritable EXE Windows est désormais obligatoire avant publication |

## Équivalences restant à démontrer

Ces lignes décrivent des limites ou des preuves absentes ; elles ne signifient pas qu’une fonction entière manque encore.

| ID | Point restant | Preuve nécessaire |
|---|---|---|
| L04/R02 | Galerie de 12 thèmes Qt ajoutée avec aperçu, personnalisation, import par famille et sauvegarde ; les ressources/métriques des skins DevExpress et certains pictogrammes restent adaptés | Comparaison visuelle sur la même machine avec une version TLE identifiée |
| L05/L07/P01/P02 | Variantes supplémentaires de layouts, images et préférences | Un export TLE réel montrant la propriété active et son résultat attendu ; tous les champs du fichier de préférences public documenté sont déjà traités |
| L06 | Nom de style sans définition embarquée | Sa définition exportable ; Fireblade accepte les bibliothèques de styles et refuse de deviner une définition absente |
| E01 | Calendriers, cultures, UTC et périodes relatives | Tests comparatifs de culture/fuseau/heure d’été avec TLE ; Fireblade conserve pour l’instant ses conventions UTC et semaine du lundi |
| E02 | Expressions dépendant d’un fournisseur externe | Fournisseur et cas réel nécessaires ; les fonctions .NET approuvées sont prises en charge, les fonctions absentes sont signalées |
| D01/D02/D03 | Variantes réelles de lecteurs et supertimelines, dépendances propriétaires/CLR4 | Entrées/sorties de référence par lecteur et version ; la matrice synthétique n’est pas une qualification de tous les exports possibles |
| D04 | Persistance d’état CLR privé ou lecteur non déterministe | Contrat de persistance du lecteur ; les valeurs déjà importées ne sont pas remplacées par une reconstruction différente |

Les plafonds documentés de Fireblade ne sont pas automatiquement des écarts avec TLE : il faut d’abord établir qu’ils y sont plus restrictifs.

## Qualifications externes

| ID | Contrôle restant |
|---|---|
| Q01 | Comparaison fonctionnelle et visuelle avec TLE sur le même poste Windows |
| Q03 | Parcours moteur Linux réussi sur 16 113 242 560 octets (15,006 GiB), 12 206 080 lignes, limite DuckDB 256 Mio : import, pages première/dernière, filtre, groupes et réouverture. Source obtenue par répétition des enregistrements du CSV publié existant, sans régénération du CSV de 3 GiB ; parcours EXE Windows de cette taille encore distinct |
| Q04 | Benchmark comparatif mémoire/import/filtres/tris/groupes/réactivité sur le même poste ; aucun gain face à TLE n’est revendiqué |
| Q05 | Essais humains prolongés, gestes Explorateur, dialogues natifs et diversité des partages Windows |
| Q06 | Apparences avec des layouts réellement exportés par l’application TLE cible |
| Q07 | Ouverture dans TLE des sessions exportées, avec lecteurs et tags réels |
| Q08 | Ouverture dans TLE des dispositions XML exportées, y compris filtres typés et règles graphiques |

Le runtime cloud reste sans contrôle du PC utilisateur ni application TLE de référence. Ses accès HTTP aux domaines officiels de téléchargement TLE et à la documentation DevExpress ne sont pas autorisés dans la configuration active ; les ajouts du brouillon d’environnement ne sont pas publiés. Ce blocage ne doit pas être confondu avec un test réussi.

La signature de code reste écartée à la demande de l’utilisateur. PDF/HTML, tags catégorisés, reprise d’import après panne et paquet autonome d’enquête ne sont pas ajoutés comme manques face à TLE sans preuve de leur présence dans TLE.
