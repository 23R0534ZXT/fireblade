# Passation — état du projet

Document de reprise, mis à jour en fin de session. Il dit où en est le code, ce
qui a été décidé, et ce qui reste. Le détail technique vit dans le skill
`fireblade-verification` ; ce fichier est la vue d'ensemble.

Dernière mise à jour : 6 novembre 2026, après la préparation de la 0.3.1.

## Où en est le projet

- **Version publiée** : 0.3.0 — `Fireblade.exe`, 280 356 023 octets,
  SHA-256 `e5198510bdb42211f79bcc9880f522330c558f5ed4fb50d624669c3f85c65aac`.
- **0.3.1** : prête sur la branche `hermes/0.3.1-full-translation` — version
  incrémentée, notes de version et README à jour, porte verte. **Pas encore
  poussée** : le mainteneur veut essayer l'application avant.
- **Vérification de référence** : 1 315 tests passés, 31 ignorés, plateforme Qt
  Windows, via `python -m scripts.dev_check` (7 min 19).

## Ce qui a été livré dans la 0.3.1

- **Toute l'interface est traduite**, plus seulement les menus : dialogues,
  gestionnaire de colonnes, préférences, chasse IOC, couverture, chronologie,
  en-têtes de tableaux, listes, infobulles, textes de saisie, messages d'état.
- **Les textes calculés à l'affichage** passent par la même table, au moyen de
  gabarits (`Analyse absente : {}`). Compteurs, fins de tâche et erreurs
  affichées sont donc traduits eux aussi.
- La couche de langue agit **à l'ouverture d'une fenêtre** (parcours de l'arbre
  de widgets) et **au moment où le code écrit le texte** (accroches sur les
  setters Qt : `setText`, `setPlaceholderText`, `addItem`, `setTabText`,
  `setHorizontalHeaderLabels`, `showMessage`, `setWindowTitle`…).
- **Double-clic sur une cellule = afficher la cellule** (texte, JSON, XML), plus jamais la note : demande explicite du mainteneur. La note et le signet passent par le menu Édition ou un clic dans la première colonne. Les guides (fr et en) ont été mis à jour en conséquence.
- Les **cinq guides intégrés** existent en anglais (`*-en.md` à côté de l'original) et `guide_path()` choisit selon la langue ; `tests/test_guides.py` vérifie que chaque guide a sa version anglaise et garde la même structure.
- Le français reste intégral : chaque libellé source est mémorisé, le retour au
  français restitue le texte d'origine.
- Six chaînes ne sont pas traduites et ne doivent pas l'être : des noms de
  fichiers d'exemple (`évidence.csv`, `résumés.csv`, `fonctions étendues.csv`)
  et deux expressions TLE synthétiques. Ce sont des données.

## Comment la traduction est outillée

- `src/fireblade/core/i18n.py` — la table `EN` (860 entrées), les gabarits à
  `{}`, `translate()` (affichage), `english()` (forme de référence),
  `has_english()` (une chaîne est-elle couverte).
- `src/fireblade/ui/language.py` — `translate_tree()` (un sous-arbre entier),
  `LanguageFilter` (traduction au `Show`, installé par `install(app)`),
  `install_hooks()` (traduction à l'écriture), `source_of()` (mémoire du libellé
  source, rafraîchie quand le code remplace le texte).
- `scripts/i18n_inventory.py` — mesure la couverture : `--missing`,
  `--by-file`, `--write-baseline`.
- `scripts/i18n_merge.py` — écrit un lot de traductions après vérification des
  clés exactes, des `{}` et des doublons.
- `tests/test_translation_coverage.py` et `tests/data/untranslated_french.txt` —
  deux garde-fous : aucune nouvelle chaîne non traduite, et la liste des
  reliquats ne peut que diminuer. Un troisième test lit la vraie fenêtre en
  anglais et échoue sur tout mot français visible.

## Ce qui reste — plan de la 0.3.2

1. « Parser un dossier » sans case : créer le case au passage (recommandé) ou
   griser le bouton avec une infobulle. Décision toujours en attente.
2. Chronologie : table en bandeau, vue d'ensemble.
3. Tests de l'exe publié et du pont .NET, reportés depuis la 0.2.x.
4. Couverture CI réelle (les qualifications Windows empruntent encore des
   chemins choisis).

## Décisions prises, à ne pas rouvrir

- L'application reste en **Qt** ; les maquettes HTML n'ont servi qu'à valider des
  structures.
- Les qualifications Windows (visuelle et 3 GiB) **fixent la langue du profil
  qu'elles créent** à `fr` : elles décrivent l'interface française.
- La suite de tests ne doit jamais pouvoir se figer sur une boîte modale ; un
  garde-fou les rejette et les nomme.
- Les dates sans fuseau sont lues comme **UTC** depuis la 0.2.3.
- **Les textes dynamiques sont traduits** eux aussi : la 0.3.1 ne s'arrête pas
  aux libellés statiques.
- **Six chaînes de données restent en français** (noms de fichiers d'exemple,
  expressions TLE) : les traduire serait faux.
- **Deux langues seulement** : anglais (référence) et français. La table reste
  une paire de dictionnaires ; une troisième langue ne demanderait pas de refonte.
- **À partir de la 0.3.2, on ne travaille plus que l'anglais.** Les nouveaux
  libellés s'écrivent directement en anglais dans le code. Le français déjà
  traduit reste affichable et ne casse rien, mais il n'est plus maintenu : une
  nouvelle chaîne n'a pas à recevoir d'entrée française, et la couverture du
  français n'est plus vérifiée. La mesure de couverture et les tests de garde
  restent utiles pour l'anglais seul (aucun texte codé en dur ne doit s'afficher
  brut dans une fenêtre anglaise).

## Pièges connus

- Ne jamais lancer deux suites de tests en parallèle : DuckDB prend un verrou
  d'écriture et la seconde bloque sans rien afficher.
- `kill` sur une session de terminal ne tue pas le processus pytest enfant ; il
  faut tuer par PID, sinon les verrous restent.
- Une fenêtre de test pilotée par type (`findChild`) casse dès que la fenêtre est
  restructurée : passer par ses méthodes.
- **Esperluettes des titres d'onglets** : Qt lit `&` comme un raccourci, on
  échappe en `&&` pour l'affichage, mais il faut mémoriser le libellé **non
  échappé**, sinon chaque passage double les `&` (`Timeline &&&& correlations`).
- **Ne pas réécrire un texte inchangé** : `setTabText` déclenche un relayout
  complet de la barre d'onglets. Une passe de langue qui réécrit chaque onglet
  fait passer un fichier de tests de 38 s à plus de 20 min.
- **Un menu ouvert en popup est sa propre racine** : `findChildren` ne le renvoie pas, donc ses entrées n'étaient jamais traduites — même piège pour une `QTabBar` posée comme racine.
- **Les guides sont empaquetés par dossier** (`docs/guides` → `resources/docs/guides`) : une liste écrite à la main laissait les versions anglaises hors de l'exe.
- Les accroches Qt sont installées **une seule fois** et ne font rien quand la
  langue est le français : c'est ce qui garde la suite rapide.

## Comment reprendre

Premier message d'une nouvelle session, suffisant pour repartir :

> Fireblade 0.3.2, la 0.3.1 est publiée, `main` est à jour. À partir de
> maintenant on ne travaille qu'en anglais. Charge le skill
> `fireblade-verification` et lis `docs/development/PASSATION.md`.

Le reste — historique, décisions, conventions — se trouve dans le dépôt et dans
la mémoire persistante.
