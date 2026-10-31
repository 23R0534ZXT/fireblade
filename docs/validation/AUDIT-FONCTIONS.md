# Vérification des fonctions et correction de l’éditeur de règles

Correctif : `1ce0e6f230c74d70719833e63c823b7b4c55c282`.

## Problème reproduit

Dans l’éditeur de règles, le remplacement du panneau de conditions conservait temporairement les anciens widgets visibles. La destruction différée peut attendre la sortie d’une boucle modale Qt. Après « Ajouter », le reproducer retrouvait trois éditeurs visibles, avec des commandes superposées. Le correctif masque et désactive immédiatement le panneau remplacé.

Le nouveau test clique sur Ajouter, saisit une condition, choisit une couleur, valide, puis contrôle la règle et les lignes correspondantes. Il vérifie qu’un seul éditeur reste visible sans forcer la destruction différée. Il échoue avec le code précédent et passe avec le correctif.

## Couverture revue

| Domaine | Vérifications existantes ou ajoutées |
|---|---|
| Coloration locale/globale | Création par l’éditeur, activation, priorité, cible cellule/ligne, adaptation des colonnes, import/export et persistance des règles |
| Filtres et recherche | ET/OU/NON, expressions, nombres, dates, regex, NULL, recherche entre analyses, récupération après erreur |
| Grille | Groupes imbriqués, résumés, tri, dépliage complet, pages profondes, cache borné, colonnes épinglées et dispositions |
| Analyse | Signets et notes, modification collective, vues, sessions, onglets et restauration après annulation |
| Formats | CSV, XLS/XLSX, BOM UTF-16/32, Unicode, grands entiers, sources inchangées, colonnes calculées et UTC |
| Windows | Trois versions Python avec Qt natif, partage SMB, chemins longs, EXE seul dans un dossier vide, thèmes et échelles |

Les tests sont accessibles sous `tests/core`, `tests/ui`, `tests/windows` et `src/fireblade/validation`. La présence d’un contrôle dans cette liste ne garantit pas toutes les combinaisons de données ou d’actions. Les dialogues système, les gestes physiques et l’usage prolongé sous Windows 10/11 restent distincts de ces essais automatisés.

Suite locale : 265 réussites, 4 contrôles propres à Windows ignorés. Les trois suites Windows ont réussi, y compris le nouveau parcours de création de règle. Le binaire autonome a passé ses 30 contrôles intégrés.

## Résultats Windows du correctif

[Exécution réussie](https://github.com/23R0534ZXT/fireblade/actions/runs/41197088449) : 268 tests réussis sur chacune des versions Python 3.11, 3.12 et 3.13 ; un test SMB réservé au job séparé. Le job de stockage natif a réussi ses trois contrôles. Les huit variantes visuelles et les 42 contrôles du CSV de 3 GiB ont réussi.

Le [rapport de charge conservé](reports/1ce0e6f-3gib.json) mesure un pic mémoire de 452,1 Mio, un import de 168,616 s et le dépliage complet avec audit/page profonde en 4,841 s. Le CSV existant a été réutilisé, sans régénération.

**Problème restant : une pause de timer de 14,953 s pendant l’import/affichage initial.** Le P95 des intervalles reste à 78 ms, ce qui ne compense pas cette longue pause. Le scénario fonctionnel passe, mais la fluidité complète n’est pas établie. Ces données synthétiques et ce runner Windows Server ne remplacent pas une qualification humaine prolongée sous Windows 10/11.

Le binaire publié a été téléchargé et son SHA-256 comparé au binaire testé : `2b0fcec84f28435e95f81e68dcc661e592ebb6aa93f056152b0ca648ee3c82ed`.
