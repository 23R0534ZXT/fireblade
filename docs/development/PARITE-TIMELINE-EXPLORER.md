# Fonctions de Fireblade face à Timeline Explorer

État du développement du 31 octobre 2026. Objectif : les usages de Timeline Explorer sur Windows avec un code modulaire et une consommation contrôlée. La présence d’un contrôle ou d’un schéma ne prouve pas une équivalence complète. La validation Windows de chaque binaire est publiée dans Actions.

Références : [manuel officiel](https://github.com/EZToolsManuals/EZToolsManuals/blob/main/manuscript/timelineexplorer.txt), [changelog](https://ericzimmerman.github.io/changelog/), [schémas de plugins](https://github.com/EricZimmerman/TLEFilePlugins/tree/7199c81ba45a97be74b4e05da43cbaabecccf5ca).

| Fonction | Fireblade | Portée et limites |
|---|---|---|
| CSV, TSV, TXT délimité | Présent | Encodages réglables, champs multilignes, lecture sans réécriture |
| XLSX | Présent | Choix de feuille ; formules comme texte |
| XLS | Ajouté | Choix de feuille ; valeurs de formules mémorisées ; pas de macros ou de styles |
| Plusieurs fichiers / onglets | Présent | Une base active ; autres onglets sous forme de snapshots |
| Ouverture de plusieurs fichiers / pendant un import | Ajoutée | File séquentielle, confirmation de chaque destination ; 1000 entrées maximum |
| Liste des onglets avec recherche | Ajoutée | Filtre sur le nom et chemin |
| Onglets sur plusieurs rangées | Ajoutés | Préférence ; lignes de barres d’onglets |
| Rouvrir le dernier onglet fermé | Ajouté | Jusqu’à 20 snapshots ; conserve vue et annotations de la base |
| Recherche dans toutes les analyses | Ajoutée | Une analyse parcourue à la fois, nombre de correspondances, ouverture du résultat ; annulation |
| Recherche dans l’analyse active | Présent | Recherche filtrante sur toutes les colonnes |
| Filtres de colonne et depuis une cellule | Présent | Inclure/exclure, y compris NULL |
| Filtres ET / OU / NON | Présent | Éditeur d’arbre, 24 niveaux et 1024 conditions |
| Expression textuelle | Ajoutée | Calculs, bit à bit, fonctions imbriquées texte/nombre/date, Iif, coalescence, Like/In/Between, champs virtuels Line/Tag/Note ; registre explicite de fonctions |
| Filtres numériques, regex et dates | Présent | Nombres exacts dans les bornes DECIMAL ; regex RE2 ; dates ISO |
| Sélection calendrier année/mois/jour | Ajoutée | Bornes inclusives/exclusives pour ne pas perdre la fin d’une journée |
| Tri multicolonne | Présent | Texte, nombre, date ISO ; 16 clés |
| Groupements imbriqués et glisser-déposer | Présent | Pagination explicite et comptages sur tous les résultats filtrés |
| Groupes par année/mois/jour/heure | Ajoutés | Les valeurs sources restent intactes ; dates invalides regroupées sous NULL |
| Résumés de groupes | Ajoutés | Non vides, distincts, somme, moyenne, minimum et maximum ; 16 résumés |
| Tri des groupes | Étendu | Valeur, effectif ou résumé ; sens réglable, départage stable |
| Déplier/replier les groupes | Étendu | Hiérarchie complète indexée sur disque, toutes les lignes accessibles dans une fenêtre paginée bornée ; repli vers l’arbre interactif |
| Colonnes visibles, ordre, largeurs | Présent | Copie et export suivent les colonnes visibles dans leur ordre visuel |
| Colonnes épinglées | Ajoutées | À gauche, modèle et sélection partagés ; état dans la vue |
| Réinitialiser les largeurs | Ajouté | Ctrl+R |
| Dispositions enregistrées | Présent | Vues dans l’analyse et fichier portable `.fireblade-view` |
| Import des layouts TLE | Partiel | Colonnes et noms de contrôles, filtres compatibles, recherche, groupes temporels, tris, résumés, règles expression/valeur ; règles graphiques non traduites refusées |
| Sessions Fireblade | Présent | Références aux bases ; données conservées séparément |
| Import `.tle_sess` | Ajouté | Sources et tags ; réimporte les sources présentes, UTF-8 pour CSV ; dispositions séparées |
| Règles de couleur locales/globales | Présent | Texte, fond, gras, cellule/ligne, priorité et partage JSON Fireblade |
| Signets / tags | Étendu | Case à cocher, sélection multiple et filtre des signets |
| Notes libres | Présent | Ajout/remplacement/retrait en masse ; export annoté |
| Booléens sous forme de cases | Ajoutés | Champs reconnus ou bascule depuis l’en-tête ; aucune mutation de la source |
| Panneau de détails | Étendu | En bas/à droite, copie et filtrage depuis un champ |
| Cellule complète, JSON, XML | Étendu | Texte brut sans troncature ; formatage limité à 2 Mo, pas de DTD/entités XML |
| Profils forensic | Étendus | 222 signatures / 193 noms ; métadonnées de présentation, pas 193 parseurs qualifiés |
| Plugins externes | Ajoutés | Profils JSON installables/rechargeables ; pas de compatibilité binaire avec les DLL TLE |
| Supertimelines | Partiel | Plaso/L2T, Psort, mactime et ForensicTimeline : dates UTC, MACB, catégories et couleurs ; valeurs sources conservées. Assemblage de dates PeScan/Wisp ; pas de chargement des DLL .NET |
| Thème et police | Ajoutés | Clair/sombre explicites, famille/taille, dates source/ISO/7 décimales |
| Copier au clic droit / en-têtes | Ajoutés | Préférences ; Maj+clic droit conserve l’accès au menu |
| Ouvrir avec / Explorateur | Ajouté | Programme choisi par l’utilisateur ; chemins locaux, aucune interprétation par shell |
| Messages | Ajoutés | Fenêtre bornée aux 500 dernières entrées ; diagnostic de démarrage conservé |
| CSV/XLSX filtré et trié | Présent | Tous les résultats, pas seulement la page visible ; colonnes visibles et ordre |
| Export des résumés et annotations | Présent | Comptages/résumés ou lignes marquées avec notes et identifiant source |
| Annulation | Présent | Requêtes, import, export, annotations, recherche entre fichiers et import de session |
| Source et provenance | Présent | SHA-256 avant/après import, source inchangée |
| Fichier Windows unique | Présent | Python/Qt/DuckDB/XLS(X), guide et licences intégrés |

## Équivalence encore à établir

La grille DevExpress de Timeline Explorer contient des possibilités qui ne sont pas intégralement inventoriées dans son manuel. Fireblade ne prétend donc pas à une parité exhaustive. Les fonctions utilisateur et agrégats de collections DevExpress, règles graphiques (barres, échelles et icônes), détails de rendu et paramètres propriétaires non traduits ne sont pas annoncés équivalents. Les parsers de textes spécialisés hors CSV et les DLL .NET TLE ne sont pas exécutés. Les heures locales sans décalage peuvent rester ambiguës ; voir COMPATIBILITE.md. La validation des gestes physiques sur Windows 10/11 et de chaque format réel reste distincte des tests automatisés.

Le dépliage complet conserve la hiérarchie sur disque et charge seulement une fenêtre de lignes ; la première indexation prend du temps et requiert du disque temporaire. Les sessions sont limitées à 1000 références et les historiques de fermeture à 20 snapshots.

La nouvelle qualification doit repasser sur le véritable EXE. Les mesures d’une ancienne préversion ne sont pas automatiquement attribuées à ce code. Une comparaison de vitesse/RAM avec la version courante de Timeline Explorer, sur le même poste et les mêmes exports, reste à réaliser.
