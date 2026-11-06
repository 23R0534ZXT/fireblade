# Passation — état du projet

Document de reprise, mis à jour en fin de session. Il dit où en est le code, ce
qui a été décidé, et ce qui reste. Le détail technique vit dans le skill
`fireblade-verification` ; ce fichier est la vue d'ensemble.

Dernière mise à jour : 6 novembre 2026, après la publication de la 0.3.0.

## Où en est le projet

- **Version publiée** : 0.3.0 — `Fireblade.exe`, 280 356 023 octets,
  SHA-256 `e5198510bdb42211f79bcc9880f522330c558f5ed4fb50d624669c3f85c65aac`.
- **Branche** : `main`, à jour, CI verte (7 jobs sur 7).
- **Vérification de référence** : 1 287 tests passés, 31 ignorés, plateforme Qt
  Windows, via `python -m scripts.dev_check`.

## Ce qui a été livré dans la 0.3.0

- Interface en anglais par défaut, français au choix dans **Préférences → Langue**.
- Barre de regroupement : niveaux numérotés, insertion par dépôt, suppression par
  niveau et bouton de suppression globale.
- Gestionnaire de colonnes à deux volets : ordre, largeur, épinglage, mémorisés
  par format d'artefact.
- Palette de commandes (`Ctrl+Shift+K`).
- Recherche inter-artefacts : affiche les événements trouvés, pas seulement un
  compteur par fichier.
- Chronologie : barres proportionnelles au volume, pistes qui remplissent la
  hauteur, barre d'actions conservée en mode chronologie seule.
- Corrections : fenêtre vide au lancement, barre « Parser un dossier » invisible,
  fantôme de glisser, refus silencieux du bouton Ouvrir, `&` dans les onglets.

## Ce qui reste — plan de la 0.3.1

Le chantier de traduction, mesuré : **602 libellés français distincts** dans
`src/`, dont environ 120 déjà couverts. **~480 restent à traduire**, surtout dans
les fenêtres de dialogue, les messages d'état et les erreurs.

1. **Deux langues seulement** : anglais (référence) et français. Pas de packs
   supplémentaires pour l'instant — la table reste une paire de dictionnaires, et
   en ajouter une troisième restera possible plus tard sans refonte.
2. **Traduction automatique des dialogues** : un filtre sur l'affichage traduit
   l'arbre de widgets à l'ouverture, sans toucher au code de chaque fenêtre.
3. **Textes dynamiques** : compteurs, messages d'état et erreurs routés par la
   table au moment où ils s'affichent.
4. Décision en attente : « Parser un dossier » sans case — créer le case au
   passage (recommandé) ou griser le bouton avec une infobulle.

Estimation : une à deux sessions, lots séparés, avec la porte de vérification
entre chaque lot.

Puis, hors traduction : chronologie (table en bandeau, vue d'ensemble), tests de
l'exe et du pont .NET reportés depuis la 0.2.x, couverture CI réelle.

## Décisions prises, à ne pas rouvrir

- L'application reste en **Qt** ; les maquettes HTML n'ont servi qu'à valider des
  structures.
- Les qualifications Windows (visuelle et 3 GiB) **fixent la langue du profil
  qu'elles créent** à `fr` : elles décrivent l'interface française.
- La suite de tests ne doit jamais pouvoir se figer sur une boîte modale ; un
  garde-fou les rejette et les nomme.
- Les dates sans fuseau sont lues comme **UTC** depuis la 0.2.3.

## Pièges connus

- Ne jamais lancer deux suites de tests en parallèle : DuckDB prend un verrou
  d'écriture et la seconde bloque sans rien afficher.
- `kill` sur une session de terminal ne tue pas le processus pytest enfant ;
  il faut tuer par PID, sinon les verrous restent.
- Une fenêtre de test pilotée par type (`findChild`) casse dès que la fenêtre est
  restructurée : passer par ses méthodes.

## Comment reprendre

Premier message d'une nouvelle session, suffisant pour repartir :

> Fireblade 0.4, la 0.3.0 est publiée, `main` est à jour. Charge le skill
> `fireblade-verification` et lis `docs/development/PASSATION.md`.

Le reste — historique, décisions, conventions — se trouve dans le dépôt et dans
la mémoire persistante.
