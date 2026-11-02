# Simplification de l’interface — novembre 2026

Cette révision applique les recommandations de l’audit GUI :

- Accueil d’un case avec import de collecte et ouverture d’export distincts.
- Sauvegarde permanente du case, de sa session et affichage de la dernière réussite.
- Navigation repliable des collectes et analyses, sans connexion aux bases inactives. Les contextes conservés portent le nom de leur règle et leur fenêtre temporelle.
- Bilan de collecte triable et filtrable, avertissements et provenance accessibles par fichier, accès aux résultats et au bilan complet.
- Étapes d’import et de détection séparées ; Hayabusa désactivé sans EVTX parsés disponibles.
- Effacement des filtres séparé de la remise à zéro de toute la vue.
- Conditions ET/OU/NON repliables, dialogue dimensionné selon l’écran.
- Règles de coloration réparties entre conditions, cible et apparence, avec options avancées et aperçu de style.
- Préférences réparties en quatre pages et commandes de compatibilité regroupées.
- Colonne de repère plus compacte et commande de repli du panneau Détails.
- Aperçu EVTX latéral réutilisable, sans nouvel onglet à chaque alerte ; conservation explicite en onglet pour sauvegarder, annoter, filtrer et exporter le contexte.
- Clic sur toute la première colonne pour surligner uniformément une ligne et conserver son signet. Le retrait d’un signet annoté demande confirmation.

## Vérifications locales

La suite complète a terminé avec **911 tests réussis et 28 ignorés**. Les **22 contrôles ignorés nécessitant les helpers .NET** ont ensuite été exécutés avec les vrais helpers et fixtures et ont tous réussi : **933 cas de test réussis au total, six non exécutés localement**. Ces six contrôles concernent Windows natif/SMB, un encodeur d’image et le jeu CSV existant de plus de 3 Gio absent du poste local.

Après les derniers ajustements de navigation et de repli, les **18 tests ciblés** des gestes utilisateur, du contexte EVTX et de l’aide intégrée ont également réussi. Le scénario de **320 analyses réelles**, la recherche entre analyses et la sauvegarde de session sont compris dans la suite complète. Les liens locaux de la documentation ont été vérifiés.

Les tests couvrent notamment :

- Clic dans la première colonne hors de la petite case à cocher ; fond uniforme, groupe déplié conservé et persistance après réouverture.
- Conservation d’une note si l’utilisateur refuse le retrait du signet.
- Conservation des groupes, du tri et des règles lors de l’effacement des filtres.
- Recherche dans le catalogue sans relire les fiches à chaque caractère ; actualisation explicite après une modification externe.
- Filtrage des résultats de collecte et consultation des diagnostics exacts.
- Consultation répétée d’un aperçu EVTX sans ajout aux onglets ou à la session, suppression du précédent aperçu temporaire, conservation explicite et reprise depuis le manifeste.
- Navigation vers la source EVTX vérifiée, retour aux alertes et suppression des seuls aperçus non conservés à la fermeture.

## Rendu et limites

Les [captures de navigation](../assets/fireblade-workspace.png), de [bilan](../assets/fireblade-collection-report.png) et de [contexte](../assets/fireblade-context-preview.png) sont rendues par Qt hors écran sous Linux sur des données synthétiques. Elles ne constituent pas des captures du véritable EXE Windows.

La grille a été examinée à 800 × 600 et les parcours complets à 1024 × 700 et 1280 × 800. Le contexte latéral demande davantage de largeur que la grille seule : sur ce rendu local, sa largeur minimale mesurée est d’environ 886 pixels logiques. La navigation se masque temporairement dans une fenêtre étroite lorsque le contexte est ouvert. Les métriques peuvent varier avec la police, le thème et Windows.

Le cache du catalogue évite les relectures de fiches pendant une recherche ; il n’est pas une mesure d’accélération générale du logiciel. Les aperçus sont limités à 1000 événements et ne gardent pas une deuxième base ouverte après leur lecture. Les filtres et exports de la grille continuent de porter sur les résultats complets.

La [qualification Windows](https://github.com/23R0534ZXT/fireblade/actions/workflows/windows.yml) du commit téléchargé reste distincte de ces tests locaux. Elle exige les sources sur trois versions de Python, le véritable EXE déplacé, les lecteurs natifs, les stockages Windows, le parcours à 320 analyses, les thèmes/DPI et le CSV de plus de 3 Gio avant publication. Le contrôle embarqué vérifie aussi le rendu de l’aperçu EVTX et sa conservation en onglet avec les véritables résultats Hayabusa.
