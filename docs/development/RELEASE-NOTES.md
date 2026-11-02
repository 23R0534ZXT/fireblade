# Fireblade 0.7.0 — Windows x64 (prototype)

## Nouveautés

- Dossiers d’enquête persistants : plusieurs collectes, sauvegardes automatiques, historique de récupération et archives portables vérifiées.
- Import Windows avec 13 EZ Tools, 70 plugins RECmd, lecteurs Shellbags et WebCache ; lecture des dossiers et archives Linux CatScale en sept familles.
- Alertes Hayabusa avec contexte EVTX et navigation vers l’événement source.
- Chronologie graphique entre analyses, corrélations et chasse de listes d’IOC.
- Rapports HTML/PDF avec annotations et provenance ; exports CSV/XLSX relus avec contrôle du contenu et empreinte SHA-256.
- Diagnostics de couverture : sources, familles attendues, erreurs et avertissements des lecteurs, dates et intégrité des exports.
- 24 palettes de thèmes, aperçu isolé, personnalisation et modes clair/sombre.

## Corrections de publication

- Les dossiers portables utilisent une copie créée par DuckDB : les bases actives restent utilisables malgré les verrous Windows.
- Le contrôle visuel attend la disposition des réglages avancés avant de tester le défilement vers leurs commandes.

## Télécharger et essayer

Télécharger **Fireblade.exe**, puis le lancer sous Windows x64. Python, Excel et une installation préalable de .NET ne sont pas nécessaires. L’interface et les guides sont en français.

[Pack de test (~5,1 Mo)](https://github.com/23R0534ZXT/fireblade/releases/download/test-pack-v1/Fireblade-Test-Pack-v1.zip) · [Retours des testeurs](https://github.com/23R0534ZXT/fireblade/issues/6) · [Signaler un problème](https://github.com/23R0534ZXT/fireblade/issues/new/choose)

## Validation du binaire 0.7.0 publié

[Construction qualifiée du commit ad1991921b615a209636f0d2c972db0002fb4fe8](https://github.com/23R0534ZXT/fireblade/actions/runs/41514474442).

Tous les contrôles requis ont réussi : sources sous Python 3.11/3.12/3.13, EXE autonome, lecteurs intégrés et matrice amont, stockage Windows, huit variantes visuelles, 320 analyses et parcours sur le CSV de plus de 3 Gio. Les rapports et captures sont joints à cette exécution GitHub Actions ; leur conservation est limitée par la politique des artefacts.

## Limites connues

Le projet reste un prototype et l’exécutable n’est pas signé. Les essais automatisés sur le runner Windows ne qualifient pas chaque poste Windows 10/11, chaque fichier endommagé ou chaque DLL tierce. Les données synthétiques et fixtures publiques ne remplacent pas vos jeux de référence.

Les résultats partiels et avertissements doivent être examinés. Les alertes ne constituent pas une conclusion de compromission. La compatibilité Timeline Explorer est partielle ; le budget DuckDB ne plafonne pas la mémoire totale du processus.

[Compatibilité et limites](https://github.com/23R0534ZXT/fireblade/blob/main/docs/development/COMPATIBILITE.md) · [Historique des lots antérieurs](https://github.com/23R0534ZXT/fireblade/blob/main/docs/archive/RELEASE-NOTES-HISTORIQUE.md)

Le workflow ajoute le commit et le SHA-256 propres au binaire lors de la publication.
