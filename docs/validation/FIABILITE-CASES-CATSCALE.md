# Audit de fiabilité : cases et collectes Windows/Linux

Le [rapport](reports/20261102-reliability-audit.json) distingue le contrôle Windows du commit de référence `ca66a54` et les nouvelles régressions locales. Les rapports Actions du commit livré restent la preuve de sa qualification Windows.

## Défauts reproduits et corrigés

- Un CSV/TSV ordinaire placé dans une arborescence CatScale pouvait être interprété comme texte CatScale et perdre ses colonnes structurées. Le lecteur natif garde désormais la priorité pour ces exports ; la timeline CSV CatScale conserve son lecteur spécialisé.
- Une limite atteinte après quelques lignes lisibles conservait ces lignes sur disque mais ne les comptait pas dans les totaux CatScale. Le comptage est maintenant incrémental et le bilan de l’entrée conserve ses lignes partielles.
- Deux membres TAR portant le même nom avaient une provenance identique. La référence contient maintenant le numéro d’entrée : `archive[entry N]!/fichier`.

Chaque correction a d’abord échoué sur un test de reproduction, puis réussi après modification.

## Scénarios renforcés

Les tests vérifient les archives de 50 hôtes, les commandes contenant des octets NUL, la libération du verrou d’un case après arrêt brutal et la cohérence de la session si le processus meurt avant le remplacement de sa fiche. Un catalogue de 300 anciens cases reste consultable sans ouvrir leurs analyses.

Le scénario mixte importe sept familles CatScale ainsi que les vrais Shellbags et WebCache de démonstration dans le même case, puis alterne douze fois avec un case indépendant. Il contrôle les neuf analyses, les deux collectes liées, les filtres, groupes, colonnes épinglées, notes et export filtré, les identifiants à zéros initiaux et les hashes des sources. Après redémarrage, les deux cases sont présents sans analyses chargées. Ce scénario est aussi obligatoire dans le véritable EXE Windows.

## Périmètre

La qualification existante couvre les 13 EZ Tools, les 70 plugins de registre, Hayabusa et son contexte EVTX, le lecteur Shellbags, WebCache, CatScale, les sessions/cases, les lecteurs TLE, les chemins Windows, 320 analyses, les thèmes et échelles d’affichage et le CSV de plus de 3 Gio. Les rapports historiques du CSV de 12,2 millions de lignes restent des essais distincts : ils ne sont pas présentés comme réexécutés lors de cet audit.

Les six tests ignorés localement concernent des fonctions natives qui exigent Windows ou un composant de plateforme. Leur exécution Windows est suivie dans Actions. Des exemples représentatifs et des tests de régression ne garantissent pas l’absence de tout bug sur toute variante d’artefact ; les avertissements de format, d’intégrité et de récupération restent à examiner.
