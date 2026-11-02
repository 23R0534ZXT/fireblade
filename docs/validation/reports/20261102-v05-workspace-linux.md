# Fireblade 0.5 — validation des outils d’enquête

Validation locale du 2 novembre 2026, à partir de `e3614d2`, sous Linux x86-64,
Python 3.12.14, DuckDB 1.5.6 et PySide6 6.12.0. Qt utilise la plateforme
`offscreen` : ces résultats ne qualifient pas le véritable EXE Windows.

La suite complète passe : **963 tests réussis, 28 ignorés**, en 163,12 secondes.
Les contrôles ciblés de l’affichage 1024 × 600, des contextes et de l’aide intégrée
passent aussi (25 tests). Les neuf contrôles de rapport PDF et de ses parcours
d’interface ont été rejoués après l’ajustement final de pagination.

Une dernière série de **17 contrôles ciblés** vérifie aussi le PDF incomplet,
les échecs de rendu, les liens de dossiers dans le catalogue et les erreurs de
nettoyage après une sauvegarde déjà validée. La destination précédente reste
intacte lors d’un export échoué.

[Résultats structurés, mesures et limites](20261102-v05-workspace-linux.json).

## Comportements vérifiés

| Fonction | Contrôles |
|---|---|
| Récupération | Historique borné à dix versions, restauration des vues, manifeste corrompu encore récupérable, refus d’une révision périmée ou d’une analyse absente |
| Sauvegarde automatique | Session effectivement écrite, désactivation conservée dans les préférences, opérations occupées exclues, erreurs conservées dans l’état de sauvegarde |
| Case portable | ZIP et SHA-256 relus avant remplacement ; vérification intégrale avant import ; conservation des annotations, vues et dispositions ; chemins réaffectés dans un nouveau case |
| Intégrité des références | Valeurs des événements et filtres sur les chemins inchangés ; contexte EVTX conservé navigable après déplacement ; nouveau contexte créé sans les anciens dossiers |
| Archives invalides | Altération d’un octet, chemins traversants, noms Windows dangereux et budget décompressé dépassé refusés ; annulation sans écraser la destination précédente |
| Chronologie | Ordre à la nanoseconde, décalages UTC, dates 1601/9999 au-delà des entiers 64 bits, lignes sans date, signets, filtres, pagination profonde et comptages complets |
| Corrélations | Utilisateurs, IP, chemins et empreintes sur plusieurs analyses ; correspondances exactes ou partielles ; valeurs SQL utilisées comme paramètres |
| Annulation | Reconstruction interrompue après insertion d’un lot : transaction annulée, ancien index conservé, fichiers temporaires supprimés |
| Navigation | Zoom, retour de période, isolation d’une piste, ouverture d’une ligne source, restauration de sa vue, séparation des cases et reprise des réglages |
| HTML/PDF | Échappement HTML des valeurs, notes et identifiants exacts, sélection/filtres et limites explicites ; PDF créé depuis le worker avec capture graphique |

Le PDF de démonstration a aussi été rendu en image pour inspection. Une extraction
de texte indépendante avec `pdftotext` retrouve les empreintes SHA-256 complètes,
les notes et les références aux enregistrements. La géométrie PDF utilise une
pagination explicite pour éviter de couper la capture graphique sur le bord A4.

## Chronologie en charge

Les sources ont été générées par `scripts.benchmarks.benchmark_timeline`. Les
utilisateurs, IP, chemins et empreintes sont synthétiques et répétitifs. Les
oracles Python vérifient les comptes, les identifiants de la dernière page,
la somme des tranches et chaque ligne de l’export filtré. Les empreintes des
sources sont inchangées après les opérations.

| Mesure | 250 000 événements | 1 000 000 événements |
|---|---:|---:|
| CSV source | 51 009 272 octets | 204 370 280 octets |
| Import de l’analyse source | 2,023 s | 7,591 s |
| Construction de l’index | 6,082 s | 23,411 s |
| Corrélation exacte d’un utilisateur | 0,242 s | 1,092 s |
| Dernière page | 0,202 s | 0,862 s |
| Densité globale | 0,201 s | 0,818 s |
| Export des correspondances | 0,253 s | 1,208 s |
| Correspondances attendues et obtenues | 2475 | 9901 |
| Pic RSS échantillonné du processus | 198,6 Mio | 210,3 Mio |

Chaque base DuckDB dispose d’un budget de **64 Mo** dans ces deux scénarios.
Ce budget ne limite pas toute la mémoire du processus. Ces mesures Linux ne
prédisent ni les données arbitraires ni les performances de l’EXE Windows.

Reproduction dans des dossiers neufs :

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m scripts.benchmarks.benchmark_timeline --directory /tmp/fireblade-timeline-1m --rows 1000000
.venv/bin/python -m scripts.benchmarks.preview_timeline --directory /tmp/fireblade-timeline-preview
```

Le second script d’interface crée six analyses réelles et 4200 événements,
capture les thèmes clair/sombre, applique une corrélation IP avec zoom et
exporte les correspondances. Les captures du guide proviennent de ce parcours.

## Périmètre à retenir

- La récupération versionne les sessions et métadonnées ; les anciennes valeurs
  des annotations et bases ne sont pas dupliquées automatiquement.
- Les archives transportent l’état courant et les résultats des collectes. Les
  artefacts bruts et plugins nécessaires à une nouvelle exécution restent à
  conserver séparément.
- Les dates non zonées sont signalées comme positions UTC supposées ; les
  conversions de fuseau explicites restent à choisir dans l’analyse source.
- Les familles d’entités sont reconnues par le nom des colonnes ; la comparaison
  exacte ne canonicalise pas les identités, adresses ou chemins.
- La chronologie est un instantané actualisable et ses résumés sont bornés.
  Les valeurs complètes restent disponibles dans les analyses originales.
- Les tests ignorés demandent notamment Windows natif, des hôtes .NET ou des
  jeux externes indisponibles ici. La construction et qualification Windows
  restent des étapes distinctes du workflow de publication.
