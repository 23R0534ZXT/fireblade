# Fireblade — prototype Windows 0.4

Les apparences des layouts TLE reprennent maintenant les images raster intégrées, les bordures, le renvoi à la ligne, les troncatures et les préfixes clavier dans la grille et les en-têtes épinglés. Les panneaux correspondants et les styles personnalisés nommés sont adaptés ; les valeurs des styles restent dans les vues sauvegardées. [Formats et limites](../guides/LAYOUTS-TLE.md).

Cette évolution complète les règles de coloration : bornes automatiques, pourcentages et percentiles exacts sur tout le résultat filtré, dégradés à trois couleurs, barres négatives avec axe zéro, trois à cinq icônes, seuils stricts/inclusifs et images PNG. Les règles se combinent par propriété, avec arrêt optionnel, police et taille propres à chaque règle. Classement, moyenne, uniques et doublons utilisent toute la population filtrée.

Les layouts TLE reprennent ces formats standards. Un pont .NET autonome importe explicitement les lecteurs TLE `ProcessFile/DataList` et leurs fonctions `Name/Evaluate`, sans installation .NET chez le destinataire. Les collections JSON acceptent les agrégats de critères, dont `Single`. Le lecteur GenericCsv amont est compilé et exécuté pendant la qualification Windows, en plus du helper intégré au véritable EXE.

Télécharger uniquement **Fireblade.exe**, puis le lancer sous Windows x64. Python, Excel et une installation préalable ne sont pas nécessaires. Le guide, les réglages par défaut et les licences sont intégrés ; les analyses et préférences personnelles sont enregistrées séparément dans le profil Windows. L’exécutable n’est pas signé.

Cette évolution complète les expressions imbriquées, les colonnes calculées persistantes et les conversions UTC avec neuf décimales et fuseaux Windows/IANA. Elle ajoute les adaptations de supertimelines, la migration des préférences `TLE_settings.xml` et des layouts TLE : colonnes, recherche, filtres compatibles, groupes, résumés et règles par valeur/expression. Les sources restent intactes et identifiées par SHA-256.

Le dépliage complet utilise un index sur disque et une fenêtre de lignes bornée. Le cache des branches ouvertes manuellement est également limité. Les lectures de pages profondes acquièrent uniquement les identifiants demandés ; un index facultatif accélère leur accès. L’ajout d’une colonne conserve la disposition de la grille. Les connexions et checkpoints passent au worker, et les alias de fichiers sont contrôlés avant export.

La publication nécessite les tests des sources sur trois versions de Python sous Windows, les chemins longs et UNC/SMB, le lancement du véritable EXE seul dans un dossier vide, les captures clair/sombre à 100/125/150/200 %, ainsi qu’un parcours sur le CSV de 3 GiB déjà publié. Ce CSV est réutilisé et vérifié par SHA-256, sans régénération. Les contrôles couvrent notamment les groupements, le dépliage complet, les filtres, tris, conversions UTC, annotations, exports, annulations et réouvertures. Les captures et mesures propres à ce commit sont dans GitHub Actions.

Le projet reste un prototype : ces vérifications automatisées ne remplacent pas une validation manuelle prolongée sous Windows 10/11 ni un benchmark face à Timeline Explorer sur le même poste. Le catalogue de 222 signatures / 193 noms n’est pas un ensemble de 193 parseurs qualifiés. Chaque DLL tierce et variante propriétaire doit encore être qualifiée ; les dépendances .NET Framework/propriétaires peuvent limiter la compatibilité. Les fonctions doivent être rechargées explicitement après réouverture. Les heures locales sans offset peuvent rester ambiguës. Voir [le suivi de parité](https://github.com/23R0534ZXT/fireblade/blob/main/docs/development/PARITE-TIMELINE-EXPLORER.md) et [les limites de compatibilité](https://github.com/23R0534ZXT/fireblade/blob/main/docs/development/COMPATIBILITE.md).


L’éditeur de règles conserve les polices absentes du poste et reste navigable à fort zoom. Les règles importées reprennent aussi les dates relatives combinées, styles texte/fond prédéfinis et moyennes inclusives. L’annulation d’une fonction .NET remonte comme une annulation et permet de recharger explicitement le plugin dans la même analyse.

Qualification de ce binaire : 317 tests réussis sur chacune des trois versions Python Windows ; trois contrôles de stockage ; 32 contrôles intégrés ; huit variantes visuelles ; 43 contrôles sur les 3 GiB existants, sans régénération. Pic du processus : 454,3 Mio ; timer P95 78 ms, maximum 3 125 ms. Une pause de plus de trois secondes reste observée. Les rapports sont conservés dans le dépôt, sous `docs/validation/reports/fe2518a-*`.


Nouveau lot : reprise automatique des DLL approuvées et des lecteurs de session ; helper CLR4 pour les anciens plugins .NET Framework ; objets et collections imbriqués dans les expressions ; icônes supplémentaires ; couleurs de thème configurables. Aucun contrôle fonctionnel n’est retiré. L’exécutable de ce lot est publié uniquement après la validation Windows du workflow.


Épinglage des colonnes à droite ajouté au menu d’en-tête, avec déplacement entre côtés et désépinglage. Les volets partagent le même modèle paginé et la sélection. Copie/export suivent l’ordre gauche, centre, droite. Vues et sessions conservent les côtés et largeurs ; les layouts TLE acceptent Fixed=Right. Les tests couvrent aussi le défilement, la sélection, le masquage, les groupes et l’ajout de colonnes calculées.

Détection automatique des lecteurs DLL par en-tête à l’ouverture et dans les sessions TLE, dès le premier fichier. Dossiers `Readers`, cache des signatures par empreinte, sonde CSV limitée à 64 Kio et import natif en l’absence de correspondance. Les lecteurs génériques sans signature ne sont pas sélectionnés automatiquement.

Mémorisation et rechargement automatiques des dispositions `.layout.local` par lecteur/profil et schéma : colonnes, masquage, épinglage gauche/droite et vue. Reprise des XML TLE locaux/default depuis les dossiers `Layouts`, priorité aux snapshots de sessions Fireblade et conservation des layouts invalides avec message.

Import TLE : tris de résumés sérialisés par index/tag, directions et multicritères propres à chaque niveau, ordre commun aux pages/dépliage/export ; apparences de lignes/groupes/cellules/en-têtes/sélection/focus, polices, alignements et dégradés. Les styles conditionnels fusionnent désormais correctement les valeurs explicites avec le style prédéfini et ses options `Use…`. Conservation dans les dispositions locales et qualification renforcée dans l’EXE.

Arguments complexes .NET natifs : références aux objets et collections du lecteur, types/méthodes/état privé/identité conservés, navigation et retours imbriqués entre DLL compatibles. Contexte chargé à la demande depuis la source approuvée, contrôle SHA-256/comptage, nettoyage des références, reprise après annulation et fermeture des processus. La qualification du fichier unique teste maintenant deux DLL distinctes et une classe CLR4. Canonicalisation des chemins du test de détection pour les chemins courts Windows.

Critères avancés DevExpress : scopes de collections et opérateurs parent `^`, existence implicite, champs sans crochets et mots réservés `@`, constantes typées/GUID/DateOnly/TimeOnly, paramètres positionnels, fonctions calendaires/mathématiques supplémentaires et alias XML respectant les contextes. Dépendances parentales reprises dans les règles paginées. Correction de l’attente du dialogue d’import dans la qualification Windows, checkpoints du rapport et arrêt complet du processus onefile après timeout.
