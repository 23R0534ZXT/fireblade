# Suivi des fonctions de Fireblade

Objectif : couvrir les usages de Timeline Explorer sur Windows, en conservant une interface classique, des modules simples et une consommation contrôlée. Ce document ne déclare pas une parité acquise. Une fonction présente doit encore être éprouvée sur les vrais exports utilisés en enquête.

| Fonction | État dans Fireblade | Limite actuelle / travail restant |
|---|---|---|
| CSV / TSV, encodages, champs multilignes | Présent | Variantes réelles et CSV endommagés à élargir |
| Import Excel | XLSX présent | XLS absent ; formules importées comme texte, mise en forme non importée |
| Plusieurs documents | Onglets présents | Un seul onglet chargé à la fois ; branches et défilement non restaurés |
| Sessions | Présent | Références aux analyses existantes, sans empaquetage de dossier d’enquête |
| Groupements imbriqués | Présent | Groupes ordonnés par comptage ; pas toutes les possibilités de résumé de la grille de référence |
| Groupement par glisser-déposer | Présent | Geste physique à vérifier manuellement sur un poste Windows |
| Recherche globale | Présent | Mode filtrant ; recherche transversale dans tous les onglets absente |
| Filtres avancés | ET / OU / NON imbriqués présents | Pas de compatibilité avec la syntaxe d’expressions de Timeline Explorer |
| Tri multi-colonnes | Présent | Nombres exacts, dates ISO ou texte, sens par colonne |
| Coloration conditionnelle | Règles locales présentes | Priorités, activation, cellule/ligne, couleurs/gras ; règles globales partagées à ajouter |
| Signets / notes | Présent | Pas de catégories de tags ni d’annotation en masse |
| Vues et disposition des colonnes | Présent | Pas d’import des fichiers de session/disposition Timeline Explorer |
| Détails et JSON | Présent | Pas de vue XML dédiée ni d’interpréteur forensic des champs |
| Profils forensic | Premiers préréglages | MFTECmd, EvtxECmd, PECmd, Hayabusa, Plaso L2T ; pas de couverture de tous les outils/versions, ni d’écosystème de plugins |
| Exports filtrés et comptages | CSV / XLSX présents | Pas de rapport HTML/PDF ni d’export direct des notes |
| Annulation et reprise | Présent | Pas de reprise après panne au milieu d’un import |
| Gros fichiers | Base sur disque et grille paginée | Comparaison instrumentée sous Windows avec Timeline Explorer et vrais CSV multi-Go à réaliser |
| Distribution Windows | Portable et CI natives | Signature, installateur, mise à jour et tests prolongés sur postes Windows 10/11 restent à faire |

Références : [présentation officielle](https://ericzimmerman.github.io/) et [historique des fonctions de Timeline Explorer](https://ericzimmerman.github.io/changelog/). L’objectif porte sur les fonctions et les usages ; il n’implique pas de réutiliser son code ou ses composants graphiques.
