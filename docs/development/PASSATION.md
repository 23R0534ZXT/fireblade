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

## Ce qui reste pour la 0.4

1. **Traduction complète** : les textes calculés à l'affichage restent en français
   (compteurs, « aucun case actif », messages d'état).
2. **« Parser un dossier » sans case ouvert** : décider entre créer le case au
   passage (recommandé) et griser le bouton avec une infobulle.
3. **Chronologie** : reste du travail graphique au-delà des barres et des pistes.

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
