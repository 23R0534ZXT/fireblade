# Utiliser Fireblade

Fireblade est un explorateur local de CSV, TSV et XLSX pour l’analyse forensic sur Windows. Il affiche une grille classique : recherche, filtres, tris, groupes, signets et notes.

## Démarrage

Télécharger `Fireblade.exe`, puis double-cliquer dessus. Python, Excel et un dossier de bibliothèques à côté du programme ne sont pas nécessaires. Le guide et les licences sont accessibles dans le menu **Aide**, même sans analyse ouverte.

Le programme prépare ses bibliothèques dans le dossier temporaire de Windows au démarrage. Cette étape peut prendre quelques secondes. Ce dossier est normalement supprimé à la fermeture. Les analyses sont enregistrées séparément pour conserver le travail.

## Ouvrir des données

1. Cliquer sur **Fichier → Ouvrir un fichier** ou appuyer sur **Ctrl+O**.
2. Choisir un CSV, TSV, TXT ou XLSX.
3. Confirmer le nom et l’emplacement du fichier d’analyse `.timeline`. Pour XLSX, sélectionner la feuille ; la première ligne doit contenir les noms de colonnes.
4. Attendre la fin de l’import. La source est lue sans réécriture.

Pour un CSV, les options permettent de préciser le séparateur et l’encodage : UTF-8, UTF-16, Windows-1252 ou Latin-1. Si la détection est ambiguë, sélectionner explicitement le séparateur. Les cellules vides sont normalisées en NULL.

Les valeurs sont conservées comme texte pour préserver les zéros initiaux et les grands identifiants. Les formules XLSX sont importées comme texte, sans calcul. Les styles et zéros provenant seulement d’un format numérique Excel ne sont pas importés. L’ancien format XLS n’est pas pris en charge.

## Rechercher et filtrer

Saisir le texte dans **Rechercher**, puis appuyer sur Entrée. Cette recherche porte sur les colonnes de l’analyse active.

Un clic droit sur une cellule permet de filtrer sur sa valeur ou de l’exclure. Un clic droit sur un en-tête ouvre les filtres de colonne. Les filtres simples se combinent par ET ; un double-clic dans leur liste retire un filtre.

**Filtres → Éditeur ET / OU / NON** permet de construire des groupes imbriqués. Un groupe NON contient exactement une condition ou un groupe. Les opérateurs comprennent recherche textuelle, égalité exacte, regex RE2, cellules vides, comparaisons numériques et bornes de dates ISO. Les données dont la conversion numérique ou temporelle est impossible ne correspondent pas à cette comparaison.

**Réinitialiser** rétablit une vue par défaut, avec les règles globales activées.

## Trier

Cliquer sur un en-tête ou utiliser son menu contextuel. Choisir le type **Texte**, **Nombre** ou **Date ISO** selon les données.

**Affichage → Tri sur plusieurs colonnes** permet d’ordonner plusieurs clés. La première a priorité, puis les suivantes départagent les valeurs identiques. Les cellules NULL viennent en dernier. Les conversions numériques évitent les arrondis en flottants des grands identifiants.

## Regrouper

Glisser un en-tête dans la barre de groupement, ou choisir **Grouper par cette colonne** dans son menu. Plusieurs colonnes créent des niveaux imbriqués.

**Regrouper…** permet de sélectionner les colonnes et leur ordre. Déplier un groupe charge une page de ses enfants ; le replier libère les descendants chargés. Les comptages des groupes portent sur les résultats filtrés, pas seulement sur les lignes visibles.

Les boutons **Suivant** et **Précédent** parcourent les pages du niveau sélectionné. **Racine** permet de revenir au niveau principal. La pagination évite de charger toute l’analyse dans la grille.

## Onglets et sessions

Chaque analyse s’ouvre dans un onglet. **Ctrl+Tab** et **Ctrl+Shift+Tab** changent d’onglet ; **Ctrl+W** ferme l’onglet actif. Attendre ou interrompre une opération avant de changer d’analyse.

Seule la base de l’onglet actif reste ouverte. Revenir à un onglet restaure sa vue et ses colonnes, puis recharge les premières pages. La sélection, le défilement et les groupes dépliés ne sont pas conservés.

**Fichier → Enregistrer la session** conserve les références aux analyses, leur ordre, les vues et la disposition des colonnes dans un fichier `.fireblade-session`. Ce fichier ne contient pas les données : conserver les bases `.timeline` référencées. Une session dont une analyse manque ou a changé est signalée.

Les règles globales appartiennent au profil utilisateur : les exporter séparément si la session doit être partagée avec la même présentation.

## Signets et notes

Un double-clic sur une ligne ouvre son signet et sa note. Dans ce dialogue individuel, une note vide retire le signet.

Pour plusieurs lignes, utiliser Ctrl/clic ou Maj/clic, puis le menu **Édition** :

- **Marquer la sélection** ajoute un signet sans effacer une note existante ; une note vide reste possible.
- **Ajouter une note** ajoute le texte après la note existante, avec un saut de ligne.
- **Remplacer les notes** remplace explicitement leur contenu.
- **Retirer les signets** supprime les signets et leurs notes sur les lignes sélectionnées.

Les en-têtes de groupes sont ignorés : sélectionner un groupe seul ne marque pas automatiquement ses descendants. La case **Signets** limite la vue aux lignes marquées.

Les notes sont conservées dans l’analyse. La grille charge seulement les annotations des pages chargées.

## Couleurs et détails

**Analyse → Règles de coloration** définit les règles locales à la vue : conditions, couleurs du fond et du texte, gras, ligne ou cellule. La première règle correspondante a priorité.

**Analyse → Règles globales** gère les règles réutilisables, leur import/export JSON et leur rechargement. Elles suivent les noms des colonnes, même si leur ordre change. Une règle dont une colonne manque est ignorée et signalée dans la barre d’état. Les règles locales sont prioritaires. L’option **Appliquer à cette vue** permet de désactiver les règles globales pour cette vue seulement.

Le panneau **Détails** affiche les valeurs complètes et la note de la ligne. **Afficher la cellule / JSON** ouvre une cellule en texte brut ou en JSON indenté, sans modifier la source. Le formatage JSON est limité à 2 Mo ; le texte brut reste disponible.

**Affichage → Appliquer le profil détecté** propose de premiers préréglages MFTECmd, EvtxECmd, PECmd, Hayabusa et Plaso L2T. Ils organisent les colonnes et le tri ; ce ne sont pas des parseurs d’artefacts bruts.

## Enregistrer et exporter

Les signets et notes sont enregistrés dans `.timeline`. **Ctrl+S** enregistre une vue nommée dans cette analyse ; **Ctrl+L** la recharge.

**Fichier → Exporter** produit un CSV ou un XLSX de tous les résultats filtrés, même si la grille n’en montre qu’une page. Pour une vue regroupée, choisir les lignes ou les comptages par groupe.

**Exporter les signets et notes** exporte les lignes marquées de la vue filtrée et ajoute trois colonnes : numéro d’enregistrement source, présence du signet et note. Le numéro correspond à l’ordre des enregistrements importés, hors en-tête ; un champ multiligne CSV peut occuper plusieurs lignes physiques.

XLSX écrit les valeurs comme texte, y compris celles qui commencent par `=`. Les résultats dépassant la capacité d’une feuille sont répartis sur plusieurs feuilles. Une cellule de plus de 32767 caractères provoque une erreur explicite : utiliser CSV pour conserver sa valeur complète.

Un export échoué ou annulé conserve l’ancien fichier de destination. La source et les analyses ouvertes ne peuvent pas servir de destination d’export.

## Interrompre une opération

Utiliser **Analyse → Interrompre la requête**. Une annulation d’import ou une erreur rouvre l’analyse précédente et sa vue. Une validation finale déjà engagée peut se terminer malgré une demande tardive. Une base vide peut rester après l’annulation d’un import.

L’annulation d’une annotation collective avant validation annule toute la sélection.

## Où se trouve le travail ?

Par défaut, Fireblade utilise le profil Windows :

- `%LOCALAPPDATA%\Fireblade\Analyses` : destination proposée pour les nouvelles analyses.
- `%LOCALAPPDATA%\Fireblade\regles-globales.json` : bibliothèque des règles globales.
- `%LOCALAPPDATA%\Fireblade\fireblade.toml` : configuration utilisateur facultative.
- `%LOCALAPPDATA%\Fireblade\Journaux\demarrage.log` : diagnostic de démarrage.

Les emplacements d’analyse, de session et d’export peuvent être choisis. Les sources peuvent se trouver sur un support en lecture seule. Sauvegarder les analyses et sessions utiles : supprimer ou remplacer l’exécutable ne supprime pas leur contenu.

## Raccourcis

| Action | Raccourci |
|---|---|
| Ouvrir des données | Ctrl+O |
| Ouvrir une analyse | Ctrl+Maj+O |
| Exporter | Ctrl+E |
| Enregistrer / charger une vue | Ctrl+S / Ctrl+L |
| Enregistrer la session | Ctrl+Maj+S |
| Éditeur de filtres | Ctrl+Maj+F |
| Marquer / retirer la sélection | Ctrl+M / Ctrl+Maj+M |
| Onglet suivant / précédent | Ctrl+Tab / Ctrl+Maj+Tab |
| Fermer l’onglet | Ctrl+W |
| Copier les lignes sélectionnées | Ctrl+C |
| Guide d’utilisation | F1 |

## En cas de problème

Si un import est refusé, vérifier le séparateur, l’encodage, l’en-tête ou la feuille sélectionnée. Un fichier déjà existant n’est pas écrasé lors de la création d’une analyse.

Si le programme ne démarre pas, consulter le journal de démarrage. Vérifier aussi que le profil utilisateur et le dossier temporaire Windows sont accessibles en écriture. Un fichier de règles invalide est laissé intact ; corriger et recharger, ou importer explicitement une bibliothèque valide.

Fireblade reste un prototype. Les tests automatisés ne remplacent pas les essais sur les exports réels de plusieurs Go et sur les postes d’enquête.
