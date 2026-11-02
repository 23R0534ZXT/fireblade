# Validation de l’import CatScale

Le lecteur Fireblade a été développé à partir des formats de `Cat-Scale.sh` à la révision `0014f234a472f536d28664902daed90527ff5858` de WithSecureLabs/LinuxCatScale. Le collecteur et ses scripts Logstash ne sont pas exécutés ou redistribués.

Le [rapport local](reports/20261102-catscale-linux.json) distingue deux essais : un corpus représentatif construit selon les commandes du collecteur, et de vraies sorties Linux obtenues avec `ps`, `/proc/self/status`, `/proc/meminfo` et `sha1sum`. Le corpus ouvre les sept familles dans les grilles Fireblade, puis vérifie les notes et la session après fermeture/réouverture du case. Les hashes des entrées restent inchangés.

Les tests couvrent aussi les modes par fichiers/par familles/grille combinée, les archives imbriquées, la provenance des membres, les chemins dangereux et liens, les binaires non reconnus, les encodages invalides, les grandes cellules, les limites et l’annulation. Le contrôle `catscale_families_import_grid_and_case_restore` exécute le même parcours dans le véritable EXE lors du workflow Windows. Le rapport local ne constitue pas un résultat Windows : consulter les rapports Actions du commit téléchargé.

Les sorties inconnues restent en lecture brute avec avertissement. Les tests ne prouvent pas la compatibilité avec toutes les distributions, langues, variantes de sortie ou versions futures de CatScale. Les binaires non pris en charge ne deviennent pas des événements analysés. Voir [le tutoriel et les limites](../guides/TUTORIEL-COMPLET.md#importer-une-collecte-linux-catscale).
