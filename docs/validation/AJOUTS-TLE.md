# Formats avancés et compatibilité TLE

Code : `fe2518a5dc14c43bce0797fe305739bc706fbfed`. Version : prototype 0.4.

## Ajouts

- Bornes fixes, automatiques, pourcentages de plage et percentiles exacts sur tout le résultat filtré, avec option de calcul sur toute la source. Cache réutilisé entre les pages et invalidé après changement de requête ou rafraîchissement.
- Dégradés à deux/trois couleurs ; barres positives/négatives, couleur négative, axe zéro ; trois à cinq icônes, seuils stricts/inclusifs, plancher, couleurs et images PNG intégrées.
- Formats statistiques : classement haut/bas, pourcentage, moyenne stricte/inclusive, valeurs uniques et doublons, choix de la casse et des NULL. Les ex æquo au seuil sont conservés ; les candidats doublons sont vérifiés sur les valeurs complètes.
- Combinaison des règles par propriété : fond, texte, police ; arrêt optionnel des suivantes. Police et taille fractionnaire propres à chaque règle. Masquer une valeur ne change ni sa copie ni son export.
- Migration des règles XML standards de TLE : valeur, expression, liste de valeurs, dates relatives combinées, statistiques, formats graphiques et styles prédéfinis. Les adaptations de palettes et pictogrammes sont documentées.
- Lecteurs DLL TLE `ProcessFile(string)` / `DataList`, sélectionnés explicitement, dans un processus .NET autonome intégré au fichier unique. Source et DLL identifiées par SHA-256 ; conversions tracées dans la provenance.
- Fonctions personnalisées `Name` / `Evaluate(object[])`, typage des opérandes et dates CLR de 100 ns. Annulation normalisée et rechargement explicite possible dans la même analyse après interruption du helper.
- Collections JSON : sélection d’objets, Count, Exists, Sum, Avg, Min, Max et Single. Pas de désérialisation arbitraire d’objets CLR depuis un layout.
- Éditeur avec sections défilantes et taille adaptée à l’écran. Les contrôles de défilement et d’enregistrement sont inclus dans la matrice Windows à 100/125/150/200 %.

## Vérifications

[Exécution Windows réussie](https://github.com/23R0534ZXT/fireblade/actions/runs/41237678884) · [EXE publié](https://github.com/23R0534ZXT/fireblade/releases/tag/prototype-fe2518a5dc14c43bce0797fe305739bc706fbfed).

- Sources : **317 tests réussis, 3 ignorés**, sur chacune des versions Python 3.11, 3.12 et 3.13. Deux tests nécessitent le helper construit ; ils sont exercés dans le build et l’EXE. Le test SMB est réservé au job de stockage.
- Stockage natif : **3 contrôles réussis**, dont le partage UNC/SMB et les chemins longs.
- Fichier unique : **32 contrôles réussis** dans le véritable EXE déplacé seul dans un dossier vide, chemins Python/.NET retirés du PATH, helper autonome réellement exécuté. [Rapport](reports/fe2518a-single-file.json).
- Lecteur public TLEFileGenericCsv compilé/exécuté avec une révision et archive épinglées. [Provenance](reports/fe2518a-upstream-plugin.json).
- **8 variantes visuelles réussies**, préférences Windows clair/sombre, zoom 100/125/150/200 %, contrôles défilants et sauvegarde des règles compris. [Matrice](reports/fe2518a-visual.json).
- **43 contrôles réussis** sur les mêmes **3 222 648 632 octets / 2 441 216 enregistrements**, avec vérification SHA-256 avant/après, sans régénération. Import : **152,600 s** ; export complet et relecture indépendante : **130,243 s**. [Rapport](reports/fe2518a-3gib.json).
- Percentiles exacts sur l’ensemble des lignes, contrôle de la page profonde et du cache : **4,147 s** ; pause maximale du timer pendant cette étape : **172 ms**.

Le pic du processus mesuré est de **454,3 Mio**, avec un budget DuckDB de 256 Mo. Le timer de 50 ms a un P95 de **78 ms** et un maximum de **3 125 ms** sur le parcours complet. Une pause de plus de trois secondes reste donc observée ; la fluidité totale n’est pas établie. Ces valeurs ne comparent pas Fireblade à TLE sur le même poste.

La Release contient uniquement `Fireblade.exe`, **114 179 101 octets**. Le fichier publié a été téléchargé et son SHA-256 correspond à celui du binaire exécuté : `2cdddd70f7e0aaf6a320fa483f5f76e6d0fa72aefeae9bf268946b8e4f30afb9`. Python, .NET et Excel ne sont pas à installer chez le destinataire. Les analyses et préférences restent des données séparées dans son profil Windows.


En complément, les contrôles locaux ont réutilisé l’analyse du CSV existant de 3 222 648 632 octets / 2 441 216 enregistrements. Les percentiles 25/50/75 de Size correspondent à un oracle numérique indépendant : `2416497291.75`, `4832994583.5`, `7249491875.25`. Une annulation pendant leur calcul a laissé zéro table temporaire et une connexion réutilisable. Les modes uniques/doublons, moyenne et classement ont également été exercés avec un budget DuckDB de 256 Mo. Ces mesures locales ne sont pas des mesures Windows.

Le lecteur GenericCsv public de TLEFilePlugins est compilé et exécuté dans le build Windows, à une révision et archive SHA-256 épinglées. Un autre contrôle utilise le helper et une DLL de qualification intégrés au véritable EXE, y compris pour les fonctions et leur annulation. Les captures, versions et conditions sont conservées dans les rapports.

Le CSV de 3 GiB est réutilisé avec vérification SHA-256 ; il n’est pas régénéré. Les petits fichiers des tests unitaires sont distincts de ce jeu de données.

## Limites précises

Le helper n’est pas un bac à sable. Les lecteurs tiers peuvent matérialiser leur DataList entière en mémoire et avoir des dépendances .NET Framework ou propriétaires incompatibles. Leur coût et leur compatibilité ne sont pas ceux du chemin CSV natif.

Les fonctions doivent être chargées explicitement après réouverture d’une analyse qui les utilise ; aucune DLL n’est lancée automatiquement depuis une vue. Les collections sont des tableaux JSON de cellules, pas les relations d’un ORM. Les pictogrammes propriétaires sont adaptés ; les styles personnalisés non traduits sont refusés. Les dates relatives sont calculées en UTC avec semaine commençant le lundi.

Ces tests automatisés ne démontrent pas une parité universelle avec toutes les versions de DevExpress, chaque DLL ou chaque export réel. Les usages prolongés sous Windows 10/11 et une comparaison instrumentée avec TLE sur le même poste restent à réaliser. Les mesures de pauses et de mémoire sont publiées sans les présenter comme une garantie de fluidité totale.

## Qualification antérieure

Le binaire `358656b` avait passé 279 tests par version Python sous Windows, 30 contrôles intégrés, huit variantes visuelles et 42 contrôles sur les mêmes 3 GiB : [exécution](https://github.com/23R0534ZXT/fireblade/actions/runs/41200337136), [rapport conservé](reports/358656b-3gib.json). Pic du processus : 448,1 Mio ; timer P95 : 78 ms ; maximum : 2 875 ms. Cette pause maximale variait jusqu’à 14 953 ms dans une qualification précédente. Ces résultats historiques ne qualifient pas le nouveau binaire.
