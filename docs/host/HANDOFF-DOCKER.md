# Passation — Fireblade en Docker (serveur), en Docker local, et en Windows

Document de passation pour un chantier de conteneurisation. Il décrit où en est le logiciel
aujourd'hui, ce que demande le schéma cible, ce qui bloque techniquement, l'architecture
proposée, un découpage en phases avec des critères d'acceptation, et les décisions à prendre.

Version de référence au moment d'écrire : **Fireblade 0.7.9**, publiée (archive Windows
283 107 207 octets, SHA-256 `22303121…d44534`), suite de tests verte (1 737 tests).

---

## 1. Le logiciel aujourd'hui

Fireblade est un poste d'analyse forensic : on ouvre un case, on y importe des artéfacts
(collectes CatScale, dossiers de journaux, images disque), on obtient des tableaux
interrogeables par artefact, on filtre, on pivote, on tague, on produit un rapport client.

Faits utiles pour la suite :

- **Techno** : Python 3.12, interface PySide6 (desktop), stockage DuckDB (un fichier par
  analyse), lecture d'artéfacts par des outils tiers .NET, un hôte C# pour les shellbags.
- **Volume** : environ 180 fichiers de tests, 1 737 tests verts, une porte de vérification
  (`vm_gate.ps1`) qui dure ~17 minutes sur la VM Windows.
- **Modèle de case** : un dossier `Cases/<identifiant 32 hexadécimal>/` contenant `case.json`
  (fiche), les dossiers de collectes, `workspace.json` (suivi d'actions), la session
  d'analyses, et les fichiers DuckDB des analyses.
- **Verrouillage** : un bail par case, implémenté par verrou de fichier, avec une branche
  `fcntl` pour Unix et `msvcrt` pour Windows — donc déjà portable.
- **Suppression d'un case** : opération livrée en 0.7.9 (3 ou 7 passes DoD 5220.22-M,
  relecture, PV hors du dossier, confirmation par saisie du nom).
- **Aucune API réseau** : rien n'écoute sur le réseau ; l'assistant IA est local par défaut.
- **Un seul analyste à la fois par case, aujourd'hui** : le bail et DuckDB en écriture exclusive
  l'imposent. Deux analystes sur deux cases différents, oui ; sur le même case, non — et c'est
  précisément ce que l'édition Server doit permettre.

Ce dernier point est le vrai sujet du chantier : le schéma cible ne demande pas seulement
« mettre Fireblade dans Docker », il demande **plusieurs analystes simultanés, y compris
plusieurs sur le même case pendant que d'autres travaillent sur d'autres cases, avec un poste
central qui gère les accès**.

---

## 2. Ce que demande le schéma cible

Lecture du schéma, composant par composant :

1. **Analystes** — accès par navigateur web, pas d'installation sur leur poste.
2. **Interface web** — HTTPS, accessible à distance.
3. **Serveur distant Linux + Docker Engine**.
4. **Fireblade, application centrale** : gestion des cases et des conteneurs, contrôle
   d'accès (RBAC), journalisation (audit logs), suppression sécurisée des preuves.
5. **Un conteneur Docker par case** : environnement isolé, volume `/data/caseN`.
6. **API Docker** : Fireblade pilote le moteur Docker pour créer, arrêter et supprimer les
   conteneurs de case.
7. **Suppression d'un case** : arrêt du conteneur, suppression du conteneur, effacement des
   données au DoD 5220.22-M (3 passes : 0x00, 0xFF, aléatoire), « données irréversiblement
   effacées et conteneur détruit ».
8. **Bénéfices annoncés** : isolation par conteneur, suppression simple et fiable, sécurité
   renforcée (HTTPS, RBAC), traçabilité complète (audit logs).

Trois éditions sont demandées au final :

- **Windows** — celle qui existe, la référence fonctionnelle ;
- **Docker serveur** — le schéma ci-dessus, plusieurs analystes, un conteneur par case ;
- **Docker auto-hébergé** — la même image sur une seule machine, pour un analyste ou une
  petite équipe, sans infrastructure.

---

## 3. Ce qui bloque aujourd'hui sous Linux

C'est le cœur du chiffrage : Fireblade n'est pas « portable en changeant le chemin des
fichiers ». Trois familles de blocages, par ordre de difficulté.

### 3.1 Les lecteurs d'artéfacts sont des exécutables Windows

Treize lecteurs sont appelés comme des programmes externes : `EvtxECmd`, `AmcacheParser`,
`AppCompatCacheParser`, `PECmd`, `MFTECmd`, `RECmd`, `LECmd`, `JLECmd`, `SrumECmd`,
`WxTCmd`, `RBCmd`, `RecentFileCacheParser`, `SQLECmd`, plus Hayabusa et un `dotnet.exe`
embarqué.

- Certains existent en build Linux (Hayabusa, et le SDK .NET peut exécuter les outils
  compilés en `net8`/`net10` sans interface graphique) ; d'autres dépendent d'API Windows.
- Le code sait déjà dire **pourquoi** un fichier n'a pas été lu (livré en 0.7.9), donc un
  lecteur manquant est visible, pas silencieux.
- L'hôte C# des shellbags est compilé `win-x64` uniquement : il faut une cible `linux-x64`
  ou un remplacement en Python.

**Décision structurante** : on ne réécrit pas treize lecteurs. On garde les outils .NET et on
les fait tourner sous Linux quand c'est possible ; pour ceux qui sont liés à Windows, on
écrit un lecteur Python de remplacement, un par un, en commençant par les plus utilisés
(EVTX et MFT). Chaque remplacement doit produire **le même schéma de colonnes** que l'outil
d'origine, sinon les filtres, les modèles de rapport et les tests existants cassent.

### 3.2 L'interface est entièrement PySide6

Environ 40 modules d'interface. Rien ne se réutilise directement sur le web : les grilles,
les menus, les dialogues, les raccourcis, le glisser-déposer, tout est Qt.

Ce qui se réutilise tel quel : `core/` — stockage des cases, moteur d'analyse, filtres,
critères, chronologie, graphe d'attaque, rapports, destruction, i18n. C'est la moitié la plus
précieuse du logiciel, et elle est déjà séparée de l'interface.

### 3.3 Les chemins et les hypothèses Windows

Profils utilisateur, dossiers `%LOCALAPPDATA%`, chemins longs, verrous, séparateurs,
encodages des CSV produits par les outils .NET, antivirus. Le code a déjà des branches
Unix par endroits (`fcntl`, séparateurs), mais il faut une passe systématique.

---

## 4. Architecture proposée — édition serveur

```
navigateur (HTTPS)
      │
      ▼
 reverse proxy (TLS)  ──►  API Fireblade (FastAPI, un processus)
                               │
                               ├── base de contrôle (cases, utilisateurs, rôles, audit)
                               ├── orchestrateur Docker (SDK docker)
                               │        │
                               │        ├── conteneur case-<id> n°1  /data/case1
                               │        ├── conteneur case-<id> n°2  /data/case2
                               │        └── …
                               └── journal d'audit (append-only)
```

Points de conception, avec leur justification :

- **Un conteneur par case, pas un conteneur par analyste.** C'est ce que dit le schéma, et
  c'est le bon choix : l'isolation suit la donnée (le case), pas la personne. Deux analystes
  autorisés sur le même case partagent le conteneur ; deux cases différents ne partagent
  rien.
- **Le conteneur de case ne publie aucun port.** Il n'est joignable que par le réseau Docker
  interne, depuis l'API. Un case n'est jamais exposé directement à un navigateur.
- **L'API ne lit jamais les preuves.** Elle gère le cycle de vie (créer, démarrer, arrêter,
  détruire) et relaie les requêtes d'analyse au conteneur du case. Le contenu reste dans le
  volume du case ; l'API ne fait transiter que des réponses demandées, avec l'identité de
  l'analyste.
- **RBAC à trois rôles au départ** : administrateur (crée et détruit les cases, gère les
  utilisateurs), analyste (travaille dans les cases où il est affecté), lecteur (consulte et
  exporte, ne modifie rien). Toute action passe par un contrôle de rôle, jamais par un test
  côté interface.
- **Journal d'audit** : qui, quoi, quand, sur quel case, résultat. Écrit en ajout seul, avec
  une empreinte chaînée (chaque entrée contient l'empreinte de la précédente), pour qu'une
  suppression d'entrée se voie. C'est ce qui rend l'argument « traçabilité complète »
  défendable.
- **Une base de contrôle séparée** des données de case : SQLite ou PostgreSQL. Elle ne
  contient que des métadonnées (identité du case, affectations, états), jamais du contenu.

### 4.1 Le conteneur de case

- Image `fireblade-case`, construite depuis le même dépôt, sans interface graphique.
- Un volume nommé par case (`case-<id>`), monté sur `/data`, avec le dossier du case à
  l'intérieur — la structure actuelle (`case.json`, collectes, analyses) ne change pas.
- Un processus unique qui expose une petite API interne (analyse, requêtes, exports) et
  meurt proprement à l'arrêt.
- Limites de ressources par conteneur (CPU, mémoire) pour qu'un case lourd ne prive pas les
  autres.
- Aucun accès réseau sortant par défaut : un case n'a aucune raison d'aller sur Internet.

### 4.2 La suppression d'un case, en conteneur

Le module de destruction existe et fait déjà le travail (3 ou 7 passes, relecture,
empreintes, PV). En conteneur, la séquence devient :

1. l'API refuse toute nouvelle session sur le case et révoque celles en cours ;
2. arrêt du conteneur du case ;
3. le volume est monté dans un conteneur d'effacement dédié, qui réécrit chaque fichier
   3 passes (0x00, 0xFF, aléatoire), relit la dernière passe, puis supprime ;
4. le volume est supprimé, le conteneur du case supprimé ;
5. un PV est écrit **hors** du volume, dans l'espace de l'API, avec les empreintes et
   l'identité de l'opérateur ;
6. l'entrée d'audit correspondante est écrite.

**Vérité technique à ne pas masquer** : sur un SSD, et plus encore sur un stockage
copy-on-write (ZFS, BTRFS, overlay), réécrire un fichier ne garantit pas que l'ancien bloc
physique disparaît. Trois parades, à trancher :

- **chiffrement par case** : chaque volume est chiffré avec une clé propre ; détruire le case
  = détruire la clé. C'est la seule méthode qui tient sur du SSD et du snapshot ;
- **volume dédié par case avec `secure discard`** : possible seulement si le matériel et le
  système le permettent ;
- **PV honnête** : dire « effacement logique vérifié au niveau fichier, plus destruction de
  la clé de chiffrement », au lieu de laisser croire à un effacement physique.

Ma recommandation : chiffrement par case dès la phase 2, et le PV mentionne les deux
opérations. C'est ce qui différencie une promesse commerciale d'une preuve.

---

## 5. Édition auto-hébergée (Docker local)

Même image, même code, un seul nœud. Différences :

- `docker compose up` sur le poste d'un analyste, accès `https://localhost` ;
- pas de RBAC multi-utilisateurs (un compte local, ou plusieurs comptes sur la même
  machine) ;
- les cases sont des volumes sur le disque local, la destruction se comporte comme
  aujourd'hui ;
- c'est la version qui sert de **rampe de test** : ce qui marche là marchera sur le serveur,
  et elle donne un produit « installez ceci sur votre poste » sans PyInstaller.

Intérêt stratégique : elle permet de valider l'image et la séparation interface/API bien
avant d'avoir un serveur multi-analystes. C'est aussi la version la plus facile à faire
tourner chez un client qui ne veut pas de serveur.

---

## 6. La stratégie d'interface

Deux options, à trancher dès le départ :

**Option A — interface web écrite à côté.** On écrit un front (une page par vue : cases,
grille d'analyse, filtres, chronologie, graphe, rapport) qui parle à l'API. L'interface Qt
reste la référence Windows. Coût élevé, mais propre, et les deux éditions peuvent diverger
sans se bloquer.

**Option B — interface web générée par le noyau existant.** On garde `core/` comme unique
source de vérité (modèles de colonnes, filtres, exports), et le front web reconstruit à
partir de ce que le noyau décrit déjà. Moins de duplication, mais demande que le noyau sache
décrire ses vues — ce qu'il fait déjà partiellement (modèles de colonnes, critères,
exports).

Ma recommandation : **Option B**, en commençant par la vue qui porte 80 % de la valeur —
la grille d'analyse avec recherche, filtres et export — puis la chronologie, le suivi
d'actions, le graphe et le rapport. L'interface Qt reste livrée et maintenue pendant ce
temps : c'est elle qui fait vivre le produit.

Ce qu'il faut éviter : réécrire l'interface web « en entier » avant d'avoir une seule vue
qui marche de bout en bout. C'est le piège classique de ce genre de chantier.

---

## 7. Plan par phases

Chaque phase est livrable seule, avec un critère d'acceptation vérifiable.

**Phase 0 — socle (1 à 2 semaines).** Découpage net : `fireblade.core` sans aucune dépendance
à Qt, importable dans un conteneur. Test qui échoue si un module de `core` importe Qt.
Image Docker de base qui démarre et répond sur `/health`. *Accepté quand* : l'image se
construit, démarre, et une commande en ligne de commande ouvre un case existant et compte
ses lignes.

**Phase 1 — API de lecture (2 à 3 semaines).** Endpoints : lister les cases, ouvrir un case,
lister les analyses, lire une page de lignes avec filtre et tri, exporter. Authentification
par jeton, RBAC minimal. *Accepté quand* : un script peut faire le parcours complet d'un
analyste sur un case réel, et refuse une action non autorisée.

**Phase 2 — un conteneur par case (2 à 3 semaines).** Orchestrateur Docker : créer, démarrer,
arrêter, supprimer un case ; volumes dédiés ; limites de ressources. *Accepté quand* : deux
cases tournent en parallèle, l'un saturé ne ralentit pas l'autre, et supprimer un case
supprime son conteneur et son volume.

**Phase 3 — destruction certifiée en conteneur (1 à 2 semaines).** Effacement 3 passes dans
le volume, PV hors volume, entrée d'audit, chiffrement par case si la décision est prise.
*Accepté quand* : une suppression réelle produit un PV, un volume vide, et une entrée
d'audit vérifiable.

**Phase 4 — interface web (4 à 8 semaines).** Grille, recherche, filtres, chronologie,
pivot, suivi d'actions, exports, rapport client. *Accepté quand* : un analyste peut traiter
un case complet dans le navigateur sans jamais ouvrir la version Windows.

**Phase 5 — lecteurs Linux (en parallèle, itératif).** EVTX et MFT en priorité, puis
Prefetch, Amcache, registre, shellbags. *Accepté quand* : sur un jeu de test commun, les
colonnes et le nombre de lignes sont identiques à la version Windows (à l'ordre près).

**Phase 6 — édition auto-hébergée (1 semaine).** `docker compose`, documentation, script
d'installation. *Accepté quand* : un poste vierge installe et ouvre un case en moins de
quinze minutes.

Ordre de valeur si le temps manque : Phase 6 peut passer avant 4 — une version locale
conteneurisée est immédiatement vendable.

---

## 8. Risques

- **Les lecteurs .NET sous Linux** (le plus sérieux). Parade : inventaire outil par outil,
  avec un test de non-régression par outil ; remplacement Python seulement là où c'est
  nécessaire.
- **Divergence des deux interfaces**. Parade : un seul noyau, et un test qui compare les
  colonnes produites par les deux chemins.
- **Performance de DuckDB dans un conteneur avec volume réseau**. Parade : volumes locaux
  sur NVMe, jamais de montage NFS pour les analyses.
- **La promesse d'effacement sur SSD**. Parade : chiffrement par case, formulation honnête
  du PV.
- **Le chantier qui n'en finit pas**. Parade : les phases ci-dessus, chacune livrable, avec
  un critère vérifiable ; ne pas fusionner deux phases.
- **Régression de la version Windows**. Parade : la porte de vérification complète reste
  obligatoire avant chaque publication, y compris pendant le chantier.

---

## 9. Décisions à prendre

1. **Chiffrement par case** dès la phase 2, ou plus tard ? (recommandé : dès la phase 2)
2. **Un conteneur par case** (schéma) ou un conteneur par analyste ? (recommandé : par case)
3. **RBAC** : trois rôles suffisent-ils, ou faut-il des rôles par case ? (recommandé :
   trois rôles + affectation par case)
4. **Base de contrôle** : SQLite au début, PostgreSQL si plusieurs serveurs ? (recommandé :
   SQLite, avec une porte de sortie propre)
5. **Interface** : option A ou B ? (recommandé : B, vue par vue)
6. **Où tourne l'IA** : dans le conteneur de case (accès réseau sortant) ou dans l'API
   centrale (le contenu transite par l'API) ? Le schéma ne tranche pas, et c'est un choix de
   confidentialité autant que technique.

---

## 10. Ce qu'il ne faut pas casser

- La version Windows reste la référence : elle est publiée, testée, et c'est elle qu'un
  client peut installer aujourd'hui.
- Le format de case (`case.json`, `workspace.json`, dossiers de collectes) doit rester
  compatible : un case créé en Windows doit s'ouvrir dans le conteneur, et l'inverse.
- La destruction reste traçable : jamais de suppression sans PV.
- La discipline de version : on accumule sur une branche, on publie une version documentée
  quand un lot est complet, et la suite complète passe avant chaque publication.

---

## 11. Où trouver les choses

- Dépôt : `23R0534ZXT/kagarasu`, branche `main`, version dans `pyproject.toml`.
- Noyau réutilisable : `src/fireblade/core/` (stockage, moteur, filtres, rapports,
  destruction, i18n).
- Interface Windows : `src/fireblade/ui/` — à ne pas toucher pendant la phase 0-2.
- Lecteurs externes : `src/fireblade/core/collection.py`, tuple `PARSERS`.
- Destruction : `src/fireblade/core/destruction.py` et `destruction_certificate.py`.
- Tests : `tests/` (180 fichiers), `harness/` pour les recettes sur la vraie fenêtre.
- Porte de vérification : `vm_gate.ps1` sur la VM Windows (~17 minutes).
- Notes de version : `docs/development/RELEASE-NOTES.md`.

---

## 12. En une phrase

Le noyau est bon et réutilisable ; ce qui manque, c'est une API, une interface web et des
lecteurs qui tournent sous Linux — trois chantiers distincts, à mener dans cet ordre, en
gardant la version Windows comme référence et en ne promettant jamais plus que ce que le
disque sait réellement effacer.
