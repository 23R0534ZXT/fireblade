Fireblade — prototype Windows x64.

Télécharger uniquement **Fireblade.exe**, puis le lancer. Python et Excel ne sont pas requis ; aucun dossier `_internal`, fichier de configuration ou script à conserver à côté du programme.

Le guide, les réglages par défaut et les notices de licence sont intégrés. Les analyses, notes et réglages personnels sont enregistrés séparément dans le profil Windows.

Cette préversion est publiée après les tests des sources sur Windows et le lancement du véritable exécutable depuis un dossier vide, sans les chemins du Python hôte. Les rapports détaillés sont disponibles dans l’exécution GitHub Actions associée au commit.

Le projet reste un prototype. Les essais utilisent notamment des données synthétiques et ne garantissent pas encore les performances sur tous les exports forensic réels de plusieurs Go ni tous les parcours Windows 10/11.

Cette préversion corrige le contraste des textes et contrôles Windows en imposant un thème clair cohérent. La publication nécessite aussi les contrôles visuels clair/sombre à plusieurs échelles et un parcours d’analyse sur un CSV synthétique varié d’au moins 3 GiB. Les captures, temps, mémoire et limites précises sont dans les rapports de l’exécution.

Le gros import est fractionné en lots bornés dans une transaction unique et les exports utilisent un seul espace de tri. Ces changements corrigent les dépassements mémoire trouvés pendant la qualification, sans augmenter le budget DuckDB par défaut de 256 MB.


Cette évolution ajoute la recherche entre analyses, les résumés et périodes de groupement, les colonnes épinglées, l’export des colonnes visibles, les préférences clair/sombre et police, les onglets sur plusieurs rangées et leur recherche/réouverture, la lecture XLS, les cases de signets et booléens, les détails XML et le filtrage depuis les détails. L’ouverture multiple utilise une file séquentielle. La distribution reste un seul Fireblade.exe.

Le catalogue de présentation comporte 222 signatures pour 193 noms de formats. Il ne correspond pas à 193 parseurs forensic qualifiés. Les profils personnels JSON sont rechargeables ; les DLL de Timeline Explorer ne sont pas chargées. La migration `.tle_sess` reprend les sources et tags ; l’import de layouts XML est limité aux propriétés de colonnes, groupes et tris. La grammaire textuelle accepte les opérateurs courants documentés, pas tout le langage DevExpress. Voir le suivi de parité dans le dépôt.

La validation du binaire inclut dix nouveaux parcours de fonctions, des captures du thème sombre et des colonnes épinglées, ainsi que des contrôles supplémentaires sur le CSV de 3 GiB : résumés comparés au générateur indépendant, groupes temporels, projection d’export et recherche entre une grande et une petite analyse. Les mesures de l’ancienne préversion ne sont pas attribuées à celle-ci : consulter ses propres rapports Actions. Des pauses longues d’interface ont été mesurées dans les qualifications précédentes ; leur disparition n’est pas annoncée.

## Extension de compatibilité en cours de qualification

Expressions imbriquées texte/nombre/date et calculs ; colonnes dérivées persistantes, conversion UTC avec précision nanoseconde et fuseaux Windows/IANA ; adaptations de supertimelines ; import de filtres, recherche, résumés et règles de valeur/expression des layouts TLE ; dépliage complet indexé sur disque. Les connexions/checkpoints natifs passent au worker et les destinations d’export sont comparées par identité de fichier, y compris leurs alias.

Les contrôles Windows ajoutés portent sur les fixtures et layouts officiels, les chemins longs et UNC et le dépliage complet sur le CSV existant de 3 GiB. La publication reste conditionnée à leur réussite ; les résultats d’anciennes versions ne prouvent pas ces changements. Les DLL .NET, fonctions personnalisées et règles graphiques DevExpress ne sont pas annoncées compatibles. L’exécutable reste un prototype 0.4 et n’est pas signé.

La migration des préférences `TLE_settings.xml` reprend aussi les tailles de police fractionnaires, les formats de dates personnalisés, les onglets, la copie, l’épinglage par défaut et les détails en haut/bas. Les adaptations de thèmes et champs non traduits sont signalées.
