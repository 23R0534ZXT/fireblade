# Passation — Fireblade, 18 novembre 2026 (nuit)

Document de reprise. Il dit où en est le dépôt, ce qui a été livré, ce qui reste ouvert,
et comment vérifier. Le détail des procédures vit dans le skill `fireblade-verification`.

## 1. État à l'instant

| Élément | État |
|---|---|
| Dépôt | `C:\Users\23R\dev\fireblade`, branche de travail `hermes/0.5.0-assistant` |
| Version dans le paquet | **0.5.0** (prototype de l'assistant local) |
| Porte locale | verte sur l'arbre 0.5.0 (ruff, fenêtre, suite complète) |
| Publication | poussée sur `main` sur demande explicite du mainteneur dans la session ; aucun tag, aucune release |

## 2. Ce que contient la 0.5.0

Un onglet **Hayabusa + AI** dans la fenêtre, avec trois vues graphiques et un assistant
local câblé mais qui ne génère encore rien.

- Constats Hayabusa **regroupés** (une règle, un hôte, une rafale) puis rassemblés en
  fenêtres temporelles ; un constat sans horodatage est compté et signalé, jamais perdu.
- **Trois vues** peintes à la main, commutables dans l'onglet : cadran du jour, carte de
  chaleur, chronologie par hôte pour une fenêtre.
- Un clic sur une marque sélectionne le constat, la grille suit, la fiche s'affiche à
  côté de la carte.
- **Paquet de preuve** déterministe : événements numérotés `[evt n]`, autres constats de
  la même fenêtre, et liste de ce qui n'a pas pu être établi.
- **Garde de citation** : une réponse dont une référence ne correspond à aucun événement
  du paquet est écartée, avec la raison.

## 3. Ce qui n'est pas fait, et ne doit pas être annoncé comme fait

1. **Aucun modèle n'est embarqué ni exécuté.** `core/assistant.py` lit `assistant.json`,
   vérifie la présence des poids et la mémoire disponible, et refuse proprement. La
   génération viendra après.
2. Pas de téléchargement du modèle à l'installation, pas de bouton « expliquer ce
   constat », pas de dialogue dans la fiche.
3. La vue « Chain » dessine l'ordre des événements d'une fenêtre ; le vrai graphe de
   liens affirmés attend le moteur.
4. Le regroupement tourne en mémoire sur l'analyse chargée. Pour des millions d'alertes
   il faudra le faire en SQL dans DuckDB.

## 4. Décisions prises dans ce cycle

- **Un seul onglet** `Hayabusa + AI`, avec le sélecteur de vue dedans. Rien d'autre à
  ouvrir pour l'utilisateur.
- **Ne jamais baisser la verbosité Hayabusa pour protéger le modèle** : on compresse les
  constats (regroupement, fenêtres), on ne jette pas de faits.
- **Le modèle ne décide de rien** : il écrit de la prose sur un paquet de preuve, et
  Fireblade vérifie chaque citation. Les comptages, tris et jointures restent du code.
- **Anglais seul** : tous les libellés de cette version sont écrits directement en
  anglais ; le test de couverture de traduction reste vert.
- Les alias de gravité français ont été retirés de `core/findings.py` : Hayabusa écrit
  `high`/`med`, et un alias français non utilisé faisait échouer le test de couverture.

## 5. Vérifier

- `set QT_QPA_PLATFORM=windows` puis `.venv\Scripts\python.exe -m scripts.dev_check`,
  ~8 minutes, doit finir par `TOUT EST VERT`.
- Les tests de cette version : `tests/test_findings.py`, `tests/test_assistant.py`,
  `tests/test_explain.py`, `tests/ui/test_hayabusa_panel.py`.
- Jamais deux suites en même temps (verrou DuckDB), et jamais `QT_QPA_PLATFORM=offscreen`
  sur la tour.

## 6. Pièges rencontrés cette nuit

- `level_of()` appliqué à une valeur déjà normalisée : la table d'alias sans la clé
  `critical` rabaissait tous les constats critiques en `informational`. Un test l'a
  attrapé, pas la relecture.
- Le test de couverture de traduction signale les phrases anglaises qui contiennent un
  mot du lexique français (« incident ») : reformuler, pas traduire.
- Un manifeste illisible renvoyait « assistant désactivé » au lieu de « installation
  incomplète » ; l'ordre des contrôles dans `status()` est maintenant explicite.
- Un test avec des horodatages fabriqués à la main (`14:249`) produisait des constats
  sans date : le helper de test génère désormais de vraies minutes.

## 7. Premier message de la prochaine session

La 0.5.0 est un prototype assumé : l'onglet et les vues fonctionnent sur une vraie
analyse Hayabusa, l'assistant explique pourquoi il ne peut pas encore répondre. Le
prochain chantier est le moteur : `llama-server` lancé par Fireblade en sous-processus,
téléchargement optionnel du GGUF à l'installation, et le bouton « expliquer ce constat »
branché sur le paquet de preuve déjà en place.
