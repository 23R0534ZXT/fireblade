# Fireblade — prototype Windows 0.5

Un nouvel onglet **Chronologie & corrélations** réunit les analyses dans un index sur disque : densité globale, pistes par analyse, signets sur le graphique, zoom à la molette, sélection de période, déplacement, historique de zoom et vue d’ensemble. Les recherches par utilisateur, IP, chemin et empreinte croisent les analyses ; chaque événement reste relié à sa ligne source. Les réglages temporels sont conservés par case, les lignes sans date restent consultables et les dates sans fuseau sont signalées. L’export CSV suit le périmètre filtré ; le graphique peut être inclus dans un rapport.

Les cases disposent d’une sauvegarde automatique toutes les deux minutes et d’un historique borné à dix versions de session. La récupération restaure les onglets, vues et métadonnées, y compris après corruption de `case.json` ; elle ne revient pas sur les annotations déjà enregistrées dans les bases. Les archives **.fireblade-case** transportent l’état courant, les analyses, annotations et résultats de collecte, avec les sources des analyses en option. Les empreintes sont relues avant publication de l’archive et vérifiées à l’import ; les références sont réaffectées dans un nouveau case sans modifier les valeurs des événements. Les artefacts bruts et les plugins nécessaires à une nouvelle exécution des parseurs restent à conserver séparément.

Les rapports **HTML et PDF** rassemblent les signets, notes ou lignes sélectionnées, la synthèse de l’enquête, les références aux enregistrements et les empreintes à l’import. Les limites et analyses indisponibles sont explicites. La capture de chronologie est facultative ; aucune conclusion de compromission n’est produite automatiquement.

La qualification de sélection à la souris utilise désormais les cellules de données : le premier bandeau de colonne sert au marquage des lignes et ne doit pas être confondu avec une sélection multiple.

La sauvegarde de session vérifie les limites de 1000 analyses et 4 Mio avant de remplacer le fichier précédent. Un dépassement conserve la sauvegarde existante et affiche une erreur ; les fichiers temporaires sont nettoyés.

L’espace de travail simplifie les parcours : deux entrées explicites pour importer une collecte ou ouvrir un export, sauvegarde permanente du case avec heure de réussite, navigation repliable par collecte et artefact/famille, bilan triable et filtrable avec diagnostics à la demande. Effacer les filtres conserve la présentation ; la réinitialisation complète est une commande distincte. Les préférences sont réparties en quatre pages et les règles suivent conditions, cible puis apparence, avec options avancées et aperçu.

Un clic dans toute la première colonne surligne la ligne complète et conserve un signet dans l’analyse. Les notes existantes sont protégées par confirmation lors du retrait du signet. Le contexte Hayabusa s’examine dans un panneau latéral réutilisable ; « Conserver ce contexte en onglet » l’ajoute à la session. Les aperçus non conservés restent temporaires. Les références EVTX et les distinctions entre alerte, candidats et voisins sont conservées.

Un onglet **Cases** conserve désormais les dossiers d’enquête sans charger leurs analyses au démarrage. Chaque case retrouve sa session, ses vues et ses annotations ; le changement de case et la fermeture enregistrent le travail. Le catalogue propose recherche, tri, modification et archivage. Les nouvelles analyses, collectes et dispositions automatiques sont rangées dans le dossier du case. Un verrou empêche son ouverture simultanée dans deux fenêtres. Le README et le tutoriel expliquent aussi les références externes à conserver dans les sauvegardes.

Le parser CatScale Linux est intégré : import de dossiers extraits et archives, onglets par famille ou grille regroupée, champs structurés pour les principaux formats et conservation explicite du texte brut restant. Les sources et lignes sont conservées, les archives sont lues sans extraction de leurs chemins et les limites/binaires non pris en charge sont signalés. Les résultats et notes se retrouvent dans les cases ; Hayabusa reste réservé aux EVTX Windows.

Les Shellbags disposent maintenant d’un lecteur hors ligne dédié dans le runtime embarqué (Registry/ExtensionBlocks), avec chemins reconstruits, MRU, références de registre, dates et octets bruts. Le WebCache ESE est lu avec dissect.esedb : tables, conteneurs, URL, dates FILETIME exactes et colonnes UTC séparées. Ces résultats se regroupent par artefact et se sauvegardent dans les cases. Les états sales, champs illisibles et limites de récupération restent signalés.

Le parcours actuel comprend l’import d’un dossier d’artefacts avec 13 parseurs EZ Tools, leur runtime et leurs maps, une organisation par onglets ou par groupes, puis la détection Hayabusa sur les EVTX vérifiés. Les alertes donnent accès à une chronologie de contexte et à la ligne EVTX source. Les références exactes, candidates et les voisins temporels sont distingués. Les résultats et journaux sont conservés dans le dossier de travail.

Le README, le guide et le tutoriel intégré présentent ce parcours avant les références avancées. Les raccourcis décrivent les actions actuelles, notamment Ctrl+Maj+E pour exporter, Ctrl+E pour effacer les filtres et Ctrl+Alt+F pour l’éditeur visuel. Les qualifications des anciens commits ci-dessous restent des archives, distinctes du workflow du commit téléchargé.

La qualification du véritable EXE exige un résultat non vide de chaque parseur et l’ouverture de chaque sortie dans la grille, ainsi que les détections Hayabusa et leur contexte. Les états du workflow Windows et ses rapports déterminent si cette qualification a réussi ; une liste de tests ne constitue pas leur résultat.

## Historique des évolutions


Les apparences des layouts TLE reprennent maintenant les images raster intégrées, les bordures, le renvoi à la ligne, les troncatures et les préfixes clavier dans la grille et les en-têtes épinglés. Les panneaux correspondants et les styles personnalisés nommés sont adaptés ; les valeurs des styles restent dans les vues sauvegardées. [Formats et limites](../guides/LAYOUTS-TLE.md).

Cette évolution complète les règles de coloration : bornes automatiques, pourcentages et percentiles exacts sur tout le résultat filtré, dégradés à trois couleurs, barres négatives avec axe zéro, trois à cinq icônes, seuils stricts/inclusifs et images PNG. Les règles se combinent par propriété, avec arrêt optionnel, police et taille propres à chaque règle. Classement, moyenne, uniques et doublons utilisent toute la population filtrée.

Les layouts TLE reprennent ces formats standards. Un pont .NET autonome importe explicitement les lecteurs TLE `ProcessFile/DataList` et leurs fonctions `Name/Evaluate`, sans installation .NET chez le destinataire. Les collections JSON acceptent les agrégats de critères, dont `Single`. Le lecteur GenericCsv amont est compilé et exécuté pendant la qualification Windows, en plus du helper intégré au véritable EXE.

Télécharger uniquement **Fireblade.exe**, puis le lancer sous Windows x64. Python, Excel et une installation préalable ne sont pas nécessaires. Le guide, les réglages par défaut et les licences sont intégrés ; les analyses et préférences personnelles sont enregistrées séparément dans le profil Windows. L’exécutable n’est pas signé.

Cette évolution complète les expressions imbriquées, les colonnes calculées persistantes et les conversions UTC avec neuf décimales et fuseaux Windows/IANA. Elle ajoute les adaptations de supertimelines, la migration des préférences `TLE_settings.xml` et des layouts TLE : colonnes, recherche, filtres compatibles, groupes, résumés et règles par valeur/expression. Les sources restent intactes et identifiées par SHA-256.

Le dépliage complet utilise un index sur disque et une fenêtre de lignes bornée. Le cache des branches ouvertes manuellement est également limité. Les lectures de pages profondes acquièrent uniquement les identifiants demandés ; un index facultatif accélère leur accès. L’ajout d’une colonne conserve la disposition de la grille. Les connexions et checkpoints passent au worker, et les alias de fichiers sont contrôlés avant export.

La publication nécessite les tests des sources sur trois versions de Python sous Windows, les chemins longs et UNC/SMB, le lancement du véritable EXE seul dans un dossier vide, les captures clair/sombre à 100/125/150/200 %, ainsi qu’un parcours sur le CSV de 3 GiB déjà publié. Ce CSV est réutilisé et vérifié par SHA-256, sans régénération. Les contrôles couvrent notamment les groupements, le dépliage complet, les filtres, tris, conversions UTC, annotations, exports, annulations et réouvertures. Les captures et mesures propres à ce commit sont dans GitHub Actions.

Le projet reste un prototype : ces vérifications automatisées ne remplacent pas une validation manuelle prolongée sous Windows 10/11 ni un benchmark face à Timeline Explorer sur le même poste. Le catalogue de 222 signatures / 193 noms n’est pas un ensemble de 193 parseurs qualifiés. Chaque DLL tierce et variante propriétaire doit encore être qualifiée ; les dépendances .NET Framework/propriétaires peuvent limiter la compatibilité. Les DLL approuvées peuvent être reprises après réouverture ; les fonctions non approuvées ou absentes restent indisponibles. Les heures locales sans offset peuvent rester ambiguës. Voir [le suivi de parité](https://github.com/23R0534ZXT/fireblade/blob/main/docs/development/PARITE-TIMELINE-EXPLORER.md) et [les limites de compatibilité](https://github.com/23R0534ZXT/fireblade/blob/main/docs/development/COMPATIBILITE.md).


L’éditeur de règles conserve les polices absentes du poste et reste navigable à fort zoom. Les règles importées reprennent aussi les dates relatives combinées, styles texte/fond prédéfinis et moyennes inclusives. L’annulation d’une fonction .NET remonte comme une annulation et permet de recharger explicitement le plugin dans la même analyse.

Archive de qualification du commit `fe2518a` (ne décrit pas le binaire courant) : 317 tests réussis sur chacune des trois versions Python Windows ; trois contrôles de stockage ; 32 contrôles intégrés ; huit variantes visuelles ; 43 contrôles sur les 3 GiB existants, sans régénération. Pic du processus : 454,3 Mio ; timer P95 78 ms, maximum 3 125 ms. Une pause de plus de trois secondes reste observée. Les rapports sont conservés dans le dépôt, sous `docs/validation/reports/fe2518a-*`.


Nouveau lot : reprise automatique des DLL approuvées et des lecteurs de session ; helper CLR4 pour les anciens plugins .NET Framework ; objets et collections imbriqués dans les expressions ; icônes supplémentaires ; couleurs de thème configurables. Aucun contrôle fonctionnel n’est retiré. L’exécutable de ce lot est publié uniquement après la validation Windows du workflow.


Épinglage des colonnes à droite ajouté au menu d’en-tête, avec déplacement entre côtés et désépinglage. Les volets partagent le même modèle paginé et la sélection. Copie/export suivent l’ordre gauche, centre, droite. Vues et sessions conservent les côtés et largeurs ; les layouts TLE acceptent Fixed=Right. Les tests couvrent aussi le défilement, la sélection, le masquage, les groupes et l’ajout de colonnes calculées.

Détection automatique des lecteurs DLL par en-tête à l’ouverture et dans les sessions TLE, dès le premier fichier. Dossiers `Readers`, cache des signatures par empreinte, sonde CSV limitée à 64 Kio et import natif en l’absence de correspondance. Les lecteurs génériques sans signature ne sont pas sélectionnés automatiquement.

Mémorisation et rechargement automatiques des dispositions `.layout.local` par lecteur/profil et schéma : colonnes, masquage, épinglage gauche/droite et vue. Reprise des XML TLE locaux/default depuis les dossiers `Layouts`, priorité aux snapshots de sessions Fireblade et conservation des layouts invalides avec message.

Import TLE : tris de résumés sérialisés par index/tag, directions et multicritères propres à chaque niveau, ordre commun aux pages/dépliage/export ; apparences de lignes/groupes/cellules/en-têtes/sélection/focus, polices, alignements et dégradés. Les styles conditionnels fusionnent désormais correctement les valeurs explicites avec le style prédéfini et ses options `Use…`. Conservation dans les dispositions locales et qualification renforcée dans l’EXE.

Arguments complexes .NET natifs : références aux objets et collections du lecteur, types/méthodes/état privé/identité conservés, navigation et retours imbriqués entre DLL compatibles. Contexte chargé à la demande depuis la source approuvée, contrôle SHA-256/comptage, nettoyage des références, reprise après annulation et fermeture des processus. La qualification du fichier unique teste maintenant deux DLL distinctes et une classe CLR4. Canonicalisation des chemins du test de détection pour les chemins courts Windows.

Critères avancés DevExpress : scopes de collections et opérateurs parent `^`, existence implicite, champs sans crochets et mots réservés `@`, constantes typées/GUID/DateOnly/TimeOnly, paramètres positionnels, fonctions calendaires/mathématiques supplémentaires et alias XML respectant les contextes. Dépendances parentales reprises dans les règles paginées. Correction de l’attente du dialogue d’import dans la qualification Windows, checkpoints du rapport et arrêt complet du processus onefile après timeout.


Les onglets multilignes défilent maintenant dans trois rangées visibles au maximum, pour conserver la grille accessible avec des centaines d’analyses. La sélection garde l’onglet actif visible et les reconstructions différées préservent le widget pendant le clic. Un test automatisé ouvre 320 CSV dans 320 analyses distinctes, navigue entre elles, recherche dans les 320 et contrôle les références sauvegardées en session. La validation locale utilise Qt hors écran ; le parcours manuel et celui du véritable EXE avec ces 320 fichiers restent à qualifier.


Lot de compatibilité : export XML déclaratif des dispositions, conservation des noms de champs/contrôles TLE et des expressions de collection inchangées, épinglage structuré par lecteur, enveloppes raster supplémentaires et import des grandes largeurs présentes dans cinq layouts publics. Les 190 layouts par défaut sont conservés sous forme d’un corpus de tests avec empreintes. Les expressions propres à Fireblade sans traduction et les options statistiques non représentables ne sont pas exportées silencieusement.

Les pages profondes dans l’ordre source utilisent désormais le même ordre temporaire d’identifiants borné que les pages triées, pour éviter de trier les valeurs larges de tous les événements. Le rechargement d’un graphe CLR vérifie aussi l’empreinte des valeurs produites à l’import ; un lecteur non déterministe est refusé avant utilisation de son nouveau graphe. Les valeurs scalaires enregistrées restent consultables. Cette empreinte couvre la projection publique sérialisée, pas un état privé arbitraire d’une DLL.

Deux qualifications Windows supplémentaires conditionnent la publication : le véritable EXE avec 320 analyses (clics, recherche, sauvegarde et restauration) et la matrice publique des lecteurs, suivie d’imports à travers le pont Fireblade. Les données des tests amont sont synthétiques ; les exports réels et les dépendances propriétaires demandent toujours des jeux de référence. Les résultats locaux Linux et les résultats natifs Windows restent identifiés séparément.


Validation locale de ce lot : 765 tests réussis, six ignorés (environnements indisponibles), helper .NET moderne testé et helper CLR4 compilé. Le moteur Linux a importé un CSV de 16 113 242 560 octets / 12 206 080 lignes sous limite DuckDB de 256 Mio, puis vérifié les pages première/dernière, filtre, groupes et réouverture. Ce jeu répète cinq fois les enregistrements du CSV publié et vérifié de 3 GiB, qui n’a pas été régénéré. Il ne constitue ni une mesure Windows du véritable EXE, ni un benchmark face à TLE. Rapports : `docs/validation/reports/20261101-*`.


Galerie de 12 thèmes : familles Office et Studio claires/sombres, bleu, argent, graphite, sable, forêt et contraste élevé. Aperçu isolé, annulation sans changement global, choix et couleurs personnalisées persistants, préférences défilables à fort zoom. L’import du nom de thème TLE choisit une adaptation de famille disponible ; aucun skin DevExpress propriétaire n’est intégré. Les contrôles du véritable EXE et de la matrice visuelle vérifient chaque palette et les boutons actifs/désactivés, avec captures.

Validation locale de la galerie : 784 tests réussis, six ignorés, dont les douze palettes et leurs boutons actifs/désactivés, l’annulation, la sauvegarde et l’accès aux commandes avec une fenêtre réduite. Le parcours Windows du commit doit réussir avant publication de son EXE.
