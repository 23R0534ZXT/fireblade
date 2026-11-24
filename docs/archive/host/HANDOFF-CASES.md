# Passation — Host en « un conteneur par case »

État au 23 novembre 2026. Écrit pour la session qui rouvre ce chantier : tout ce qui a
été décidé, mesuré ou écarté est ici, rien n'est à redécouvrir.

## Ce qui est décidé

- Le Host passe de **un conteneur, N cases** à **un conteneur par case ouverte**.
- Plusieurs cases peuvent être ouverts en même temps (le Host n'est pas limité à un),
  donc plusieurs conteneurs de case en parallèle, avec un plafond réglable.
- **Supprimer** un case, avec ou sans DoD, supprime **aussi son conteneur et son volume**.
  Il ne doit rien rester : ni dossier, ni export, ni archive, ni annexe.
- Le **chiffrement de volume** n'est pas dans ce lot : il appartient à la session suivante
  (0.9.0 — le lot par case a pris le 0.8.0).
- Un seul verbe pour supprimer : **erase**. L'archivage n'est plus offert par le client Host ;
  la liste garde le statut et le filtre, parce qu'un case archivé depuis le Desktop reste
  lisible.
- Le lot sort en **0.8.0**, avec ses notes de version.

## Le raisonnement, en trois phrases

Un case est un objet isolé : un conteneur par case donne l'isolation des ressources, rend
la destruction vérifiable (on supprime un objet, pas des fichiers épars) et permet de
limiter mémoire et CPU par affaire. Le prix est un pilote qui parle à Docker et un peu de
latence à l'ouverture. Le reste — DuckDB, lecteurs, certificat — ne change pas.

## Architecture cible

```
                navigateur
                    │
              ┌─────▼──────┐        pilote (processus hôte, ou conteneur « driver »)
              │   driver   │  - liste, crée, détruit les cases
              │  :8080     │  - démarre/arrête un conteneur par case
              └──┬──────┬──┘  - proxifie /case/<id>/… vers le conteneur du case
                 │      │
   réseau privé  │      │  volume des certificats (hors des cases)
   fireblade-…   │      └──────────────► /srv/fireblade/certificates/
                 │
      ┌──────────▼───────────┐   ┌──────────────────────┐
      │ fireblade-case-<id8> │   │ fireblade-case-<id8> │   … un par case OUVERT
      │  image fireblade:host│   │                      │
      │  volume du case seul │   │                      │
      └──────────────────────┘   └──────────────────────┘
```

### Les volumes

Un volume par case, et **un seul** :

```
/srv/fireblade/volumes/<id>/
    <id>/                ← le case, tel que le Desktop l'écrit
    exports/             ← ce que les exports du case ont produit
    archives/            ← les archives du case
    certificates/        ← les annexes photo du certificat de destruction
```

Le conteneur du case monte ce dossier en `/data/library` et tourne avec
`--root /data/library` : **le volume *est* la racine de bibliothèque** (le service lit les
cases à la racine, il n'y a pas de sous-dossier `cases/`). Conséquence : **tout ce que le
case produit naît dans son volume**, y compris les exports et les archives. Supprimer le volume, c'est supprimer le case et ses
traces, sans balayage à faire ailleurs.

### Le cycle de vie

1. **Ouvrir** : le pilote cherche le conteneur `fireblade-case-<id8>` ; s'il n'existe pas, il
   le crée (`docker run -d --label fireblade.case=<id> --label fireblade.role=case
   --network fireblade-cases -v <volume>:/data/library fireblade:host --root /data/library`),
   attend `/health` (2 à 5 s), puis proxifie.
2. **Fermer** : le conteneur peut rester (rouvrir est instantané). Le pilote en arrête
   d'autres si le plafond est atteint (le plus ancien inutilisé d'abord).
3. **Supprimer** :
   `docker stop` → `docker rm` → effacement du volume (DoD 3 ou 7 passes via
   `core.case_destruction`) → suppression du dossier du volume → `docker volume rm` (ou
   suppression du dossier si bind mount) → certificat écrit dans le volume du pilote.
   Le certificat est la seule chose qui survit, et il vit **hors** du case.
4. **Au démarrage du pilote** : réconciliation. Un conteneur étiqueté dont le case n'existe
   plus est arrêté et supprimé ; un volume sans case est signalé, jamais supprimé
   silencieusement.

### Le routage et le client

Le client actuel appelle des chemins absolus (`/api/cases/…`, `/health`, `/api/tasks/…`).
Deux options, la seconde est retenue :

- proxifier chaque route du service — fragile, les tâches (`/api/tasks/<job>`) n'ont pas
  d'identifiant de case et ne peuvent pas être routées ;
- **servir l'application entière depuis le conteneur du case**, sous le préfixe
  `/case/<id>/`, et rendre le client conscient du préfixe : une fonction
  `url(path)` qui préfixe tout chemin commençant par `/`, utilisée dans `api()`,
  `apiAbortable()` et les `fetch` directs (import de paquet, règles globales, photos).
  Avec un préfixe vide, le comportement actuel est inchangé — le Host mono-conteneur
  continue de fonctionner.

La page du pilote (`/`) est une petite page serveur : la liste des cases, créer, ouvrir
(→ `/case/<id>/`), détruire. Elle n'a pas besoin du client complet.

## Où en est le lot (23 novembre, fin de session)

Le lot est **écrit, testé et joué sur docker01** ; il attend le commit et la revue visuelle.

- Lot « résidus » **gardé** : `outside_entries()`, `destroy_case(..., extras=...)`,
  `GET /api/cases/{id}/residue`, le dialogue qui annonce ce qui vit hors du dossier.
  Les photos du certificat sont lues **avant** la destruction de l'annexe (`images=` dans
  `build()`), sinon le document perd ses preuves.
- `src/fireblade/web/agency.py` : le pilote (`Docker` en sous-processus, `CaseContainer`,
  `Volumes`, `Agency`), sa page, le proxy `/case/<id>/…` et l'interception du
  `POST /api/cases/<id>/destroy` venu du client.
- Client : `url()` préfixe tout chemin absolu ; `index.html` charge `static/…` en relatif ;
  le test de contrat `test_every_request_carries_the_case_prefix` interdit un `fetch` nu.
- Images : `deploy/host/Dockerfile.driver` (docker CLI statique + FastAPI + httpx + le core
  qui détruit, ~320 Mo) et `deploy/host/docker-compose.driver.yml` (socket, volumes,
  certificats). `bash /root/build_driver.sh --run` sur CT102 construit et lance le pilote
  sur docker01:8096.
- Tests : 11 dans `tests/web/test_agency.py` (faux binaire docker), 129 tests web au total.
- Recette faite : deux cases = deux conteneurs, isolation vérifiée, effacement DoD d'un case =
  conteneur + volume + dossier + paquet portable + archive disparus, certificat dans
  `/srv/fbcertificates`, l'autre case intact, le Host mono-conteneur toujours vert (9 cases).
- Reste : la porte complète sur l'arbre final, le commit sur `feat/cases-per-container`,
  la revue visuelle de l'utilisateur, puis la fusion sur `main` en 0.8.0.

## Ordre de travail, et où il en est

1. Lot « résidus » — **fait**, gardé, porte verte.
2. `fireblade/web/agency.py` — **fait** : `Docker` (CLI en sous-processus), `CaseContainer`,
   `Volumes`, `Agency`, page du pilote, proxy, interception de l'effacement.
3. Préfixe côté client — **fait**, avec le test de contrat `test_every_request_carries_the_case_prefix`.
4. `deploy/host/Dockerfile.driver` et `docker-compose.driver.yml` — **faits**, image construite
   et pilote lancé sur docker01:8096.
5. Destruction — **faite**, `core.case_destruction` réutilisé tel quel, certificat hors volume.
6. Recette — **faite** (voir plus haut), captures dans `/root/recette-cases/`.
7. Notes de version (0.8.0) + `HOST-EDITION.md` + README de `deploy/host` — **faits**.
8. Reste : porte complète sur l'arbre final, commit sur `feat/cases-per-container`, regard
   de l'utilisateur sur la fenêtre et sur la page du pilote, puis fusion en 0.8.0.

## Ce qu'il ne faut pas refaire (déjà mesuré)

- **Le socket Docker, c'est root sur l'hôte.** Acceptable pour un analyste seul sur sa
  machine (édition Host). Pour l'édition Server, le pilote tourne sur l'hôte, pas dans un
  conteneur — c'est déjà écrit dans `HANDOFF-DOCKER.md`.
- **`scp` conserve le mode du fichier** : une couche web copiée en `600` rend l'image
  inutilisable pour l'uid 10001 (`PermissionError: /app/src/fireblade/web/__init__.py`).
  `build_host.sh` fait maintenant `chmod -R a+rX` sur le contexte.
- **Un seul exemplaire des sources** : `build_host.sh` prenait la couche web sur CT102 et
  le noyau sur la VM ; il prend désormais tout sur la VM. Deux copies = un correctif qui
  n'arrive jamais dans l'image.
- **Le DoD n'efface pas un SSD.** Il réécrit les blocs logiques ; le wear levelling et les
  systèmes copy-on-write gardent des copies. Le certificat le dit. La réponse qui tiendra
  est le volume chiffré par case — session 0.8.0 : LUKS par volume, clé en mémoire,
  destruction = clé jetée, DoD par-dessus pour la forme.
- **`window.prompt` bloque le client CDP** : les dialogues du client sont des modales
  maison, ne pas y revenir.
- Le certificat s'écrit **avant** la disparition du dossier qu'il décrit, et **hors** de
  lui.
- **`python:3.12-slim` n'a pas la CLI docker** : le pilote échoue au démarrage
  (`docker is not available`). Le Dockerfile du pilote prend le binaire statique.
- **Un volume créé par root est illisible pour l'image** (uid 10001) : le case se liste en
  `Permission denied`. Le pilote passe le volume à `--case-uid/--case-gid` (10001).
- Même piège pour un Host monté sur un dossier neuf de l'hôte : l'image a désormais un
  entrypoint (`deploy/host/docker-entrypoint.sh`) qui prend une fois possession de
  `/data/cases` et `/data/plugins`, puis abandonne le privilège pour l'uid 10001. Ne pas
  remettre `USER fireblade` dans le Dockerfile.
- **Le daemon ne connaît que les chemins de l'hôte** : un pilote conteneurisé monte
  `/srv/fbvolumes/<id>`, pas `/data/volumes/<id>` (`--host-volumes`). Même chose pour le
  chemin du certificat rendu au client (`--host-certificates`).
- **Le case ne peut pas détruire son propre conteneur** : le `POST …/destroy` préfixé est
  intercepté par le pilote avant le proxy. Sans ça, le conteneur efface son case dans son
  volume et laisse orphelin conteneur + volume.
- **Le volume *est* la racine de bibliothèque** (`--root /data/library`), pas
  `/data/library/cases` : la correction du schéma de la passation précédente, vérifiée sur
  le service.

## Repères

- Dépôt : VM `fb@192.168.1.80`, `C:\Users\fb\dev\fireblade` ; git dans
  `C:\Users\fb\tools\git\cmd\git.exe` ; portaile : `python -m scripts.dev_check`.
- Host actuel : docker01 `192.168.1.201`, conteneur `fireblade-host`, port 8095,
  `/srv/fbcases` ↔ `/data/cases`, 9 cases, version 0.7.9.
- Image : 1,13 Go ; reconstruction ~4 min avec le cache ; `bash /root/build_host.sh` sur
  CT102 (source unique : la VM).
- Rapports et captures de la recette Desktop/Host : `/root/recette/`,
  archive `/root/recette-fireblade.tgz`.
- Documents de l'édition : `docs/host/` (EDITION, AUDIT, PARITY, LINUX-READERS, BETA,
  HANDOFF-DOCKER, HANDOFF-HOST).

## Définition de « fini » pour ce lot

- Deux cases ouverts en même temps, chacun dans son conteneur, sans mélange de données.
- Suppression DoD d'un case : conteneur, volume, dossier et exports disparus ; certificat
  présent ; l'autre case toujours lisible, ses conteneurs intacts.
- Aucun conteneur orphelin après redémarrage du pilote.
- Le Host mono-conteneur reste utilisable (préfixe vide) : pas de régression.
- Porte complète verte sur la VM, et la recette refaite avec captures.
