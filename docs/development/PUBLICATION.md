# Publier une version

## Contrôles et release sont deux opérations distinctes

Les PR et les modifications de code sur `main` exécutent les contrôles Windows. Une modification de `README.md`, de `docs/` ou des notices seule ne lance pas toute la construction sur un push. Une construction ordinaire réussie conserve l’EXE dans les artefacts Actions et ne crée pas de release publique.

La publication nécessite un tag `vX.Y.Z`, ou un lancement manuel du workflow **Windows tests and standalone EXE**, sur `main`, avec **publish_release** activé. Le mode **profile_only** ne publie rien. Tous les contrôles requis, dont Ruff, doivent réussir avant le job de publication.

## Préparer la version

1. Mettre la même nouvelle version dans `pyproject.toml` et `src/fireblade/__init__.py`.
2. Actualiser `docs/development/RELEASE-NOTES.md` : nouveautés, corrections, limites et validations de cette version. Les anciens lots sont dans `docs/archive/RELEASE-NOTES-HISTORIQUE.md`.
3. Intégrer les changements sur `main`. Choisir un numéro inédit : une version déjà publiée n’est pas remplacée. La 0.7.0 actuelle utilise encore son ancien tag `prototype-ad1991921b615a209636f0d2c972db0002fb4fe8` ; elle est conservée telle quelle.
4. Créer puis pousser un tag sur le commit retenu, par exemple `git tag v0.7.1` puis `git push origin v0.7.1`.
5. Attendre le succès de l’exécution liée au tag. La release est préparée en brouillon, avec `Fireblade.exe`, puis rendue publique après l’envoi réussi. Le titre indique la version ; les notes indiquent le commit et le SHA-256 du fichier.
6. Vérifier le téléchargement, puis actualiser les liens du README et de l’issue des testeurs vers cette release.

Un tag différent de la version du code est refusé. Les préversions restent identifiées comme prototypes. Les packs de données conservent leurs publications séparées ; leurs liens doivent rester disponibles lors du nettoyage des releases de l’application.

## Pack de test

Le workflow **Publish downloadable forensic test pack** construit et valide un candidat avec une application qualifiée disponible. Le commit, le tag de release et le SHA-256 de référence sont définis une seule fois dans `scripts/test_pack/package.py` ; le checkout des sources et le téléchargement de l’EXE utilisent ce même commit. Le validateur vérifie le SHA-256 avant d’utiliser les moteurs embarqués.

Sur un push, ou sur un lancement manuel sans **publish_pack**, le résultat reste un contrôle avec des rapports Actions. Le pack v1 déjà publié reste inchangé et téléchargeable, avec sa provenance historique d’origine.

Pour publier un nouveau pack, augmenter sa version dans le générateur et le workflow (nom d’archive, tag, guide, manifeste et notes), actualiser la référence qualifiée si nécessaire, puis lancer manuellement avec **publish_pack**. Le workflow refuse de remplacer une publication existante. Ne pas renommer silencieusement le pack v1 ni réutiliser son tag pour un nouveau contenu.

## Dépendances et qualité

`python -m ruff check src scripts tests` vérifie les erreurs de syntaxe et de noms sans exiger un reformatage global. Dependabot propose chaque semaine les mises à jour des dépendances Python déclarées dans `pyproject.toml` et des actions GitHub. Les versions de production restent épinglées dans `requirements/runtime.txt` : une PR de dépendance doit actualiser ces épingles de façon cohérente, puis passer les contrôles avant intégration.

Les mises à jour automatiques ne sont pas fusionnées automatiquement. Conserver les sources et empreintes des moteurs dans `config/forensic-toolchain.json`.
