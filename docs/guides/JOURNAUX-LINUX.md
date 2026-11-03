# Journaux Linux `/var/log/`

## Importer

Dans **Importer une collecte**, sélectionner une copie hors ligne du dossier
`var/log`, puis un dossier de travail distinct. Garder le chemin `var/log/`
permet de reconnaître également les fichiers applicatifs sans extension.
Un dossier nommé `log`, les noms usuels (`syslog`, `messages`, `wtmp`…),
les fichiers `*.log` et les journaux `*.journal` sont aussi reconnus séparément.
Une archive peut être nommée `var-log.tar.gz`, `var-log.tar.xz`,
`var-log.tar.zst`, `linux-logs.tar` ou une variante équivalente.
Les archives CatScale conservent leur lecteur et leurs limites existantes.

Les fichiers ne sont jamais exécutés ni modifiés. Les liens et fichiers spéciaux
(socket, FIFO, périphérique) ne sont pas suivis. Les empreintes SHA-256 de collecte
encadrent le traitement. Le rapport distingue lecture structurée, lecture brute,
fichier vide, erreur, format binaire inconnu et membre ignoré.

## Couverture du lecteur LinuxLogs

| Format | Lecture |
| --- | --- |
| Syslog traditionnel, timestamps ISO, RFC5424 | Date source, hôte, processus, PID et message ; structured data RFC5424 séparée du message et conservée dans `Champs` |
| Linux audit | Une ligne par record, champs et identifiant d’événement ; les records ne sont pas fusionnés par proximité |
| Apache/Nginx access standard | Adresse, utilisateur, date, requête, statut, octets et complément brut |
| Apache/Nginx error standard | Date, niveau et détail ; PID lorsqu’il est explicite |
| JSON Lines | Objet complet dans `Champs`, champs usuels projetés dans les colonnes |
| Zeek TSV avec `#separator`/`#fields` | Colonnes déclarées, timestamp source et adresse d’origine |
| W3C extended avec `#Fields:` | Colonnes déclarées, date/heure et principaux champs HTTP |
| Kernel/dmesg | Temps monotone conservé ; aucune conversion inventée en date civile |
| Application avec date initiale | Date et message ; schéma métier non supposé |
| systemd `.journal` | Objets réguliers et compacts, données non compressées, XZ, LZ4 et Zstandard ; décodage direct également sous Windows |
| Journal Export Format | Champs répétés et champs binaires avec longueur explicite |
| utmp/wtmp/btmp | ABI Linux glibc little-endian de 384 octets ; type, PID, utilisateur, terminal, hôte et date UTC |
| Comptabilité des processus `acct`/`pacct` | Linux `acct_v3` little/big-endian déclaré par le record ; PID, PPID, UID, commande, début, durée, compteurs et code de sortie |
| lastlog | ABI Linux glibc little-endian de 292 octets ; UID par position, terminal, hôte et date UTC |
| Texte non reconnu, continuation, trace applicative | Une ligne brute avec source, ligne et offset ; pas d’abandon silencieux |
| Autre binaire ou ABI non reconnu | Refus ou erreur explicite, conservation de la source originale |

Rotations gzip, bzip2, XZ/LZMA, Zstandard et LZ4, y compris les flux concaténés. Les troncatures et données finales invalides BZip2/LZ4/Zstandard sont signalées. Les archives ZIP sont également parcourues hors ligne, avec contrôle de leur index avant son chargement ; les entrées chiffrées ou spéciales sont refusées.
Les TAR sont parcourus en flux sans extraire leurs chemins sur disque.
Les chemins dangereux, liens et membres spéciaux ou sparse sont signalés.
Les champs non projetés restent dans le texte brut ou les champs JSON. Les textes UTF-16/UTF-32 avec BOM conservent leurs offsets en octets. Les messages SSH, sudo, UFW et CEF reçoivent des colonnes dédiées lorsque leur syntaxe correspond au schéma reconnu. Les chemins et proctitle audit encodés en hexadécimal sont décodés, tout en conservant les champs sources.
Les enregistrements utmp/lastlog gardent les octets sources en hexadécimal.

## Gros volumes et limites

Le texte est lu ligne par ligne. Les CSV puis les bases d’analyse sont écrits sur
le disque. Une ligne est limitée à **8 Mio**, une entrée binaire développée à
**64 Mio**, un parcours à **100 000 membres**, et la profondeur à **8 couches**.
Le budget de lecture/décompression par source est de **1 Tio**, en comptant les
couches traversées. Il n’y a pas la limite CatScale de 256 Mio par membre ni de
4 Gio pour le lecteur LinuxLogs. Ces limites déclenchent un diagnostic, jamais
une mention de réussite intégrale.

Un journal systemd ordinaire est lu directement avec accès aléatoire. Un journal
contenu dans une compression/archive est temporairement copié sur disque pour
cet accès. Prévoir de l’espace pour les données développées, les CSV, les copies
enrichies et les bases ; il n’existe pas de ratio fixe de taille. L’import conserve
les limites générales de Fireblade, notamment 1 000 analyses ouvertes.
Pour une collecte comportant davantage de fichiers, répartir les imports.

Un résultat partiel précédant une erreur reste identifiable dans le rapport.
Les lignes brutes et les erreurs produisent des avertissements visibles dans
**Couverture & diagnostics** et le détail du fichier. Le profil
**Journaux Linux /var/log/ attendus** permet de vérifier la présence du lecteur.

## Interprétation et état de qualification

Une date syslog sans année reste sans année. Une date sans fuseau reste sans
fuseau. Les dates audit/Zeek restent des valeurs Unix source, avec une projection explicite dans `Horodatage UTC`. Les dates binaires
utmp/journal sont exprimées en UTC. Les colonnes de la chronologie doivent être
choisies selon ces sémantiques ; un temps monotone n’est pas une date civile. La colonne `Horodatage UTC` est reconnue par la chronologie. La précision sous la microseconde des dates source explicitement zonées ou Unix est conservée dans cette projection. Une clé explicite permet de rapprocher les records audit d’un même événement ; elle ne constitue pas un assemblage automatique de l’événement complet.

Les schémas personnalisés, autres ABI utmp/lastlog, fichiers propriétaires et
formats futurs ne peuvent pas être garantis. Les continuations ne sont pas
assemblées automatiquement. La décompression et le décodage d’un journal systemd
ne vérifient pas ses hachages internes ni son scellement cryptographique.
Les octets UTF-8 invalides sont affichés avec des échappements, sans suppression.

## Reproduire les contrôles

```sh
python -m pytest tests/core/test_linux_logs.py tests/ui/test_linux_logs_desktop.py -q
python -m scripts.benchmarks.linux_logs --directory artifacts/linux-stress --gib 32 --import-rows 200000 --report artifacts/linux-log-qualification.json
```

Le premier volet de la mesure vérifie et hache les enregistrements décodés d’une
source compressée unique de 32 Gio, avec des lignes synthétiques de 1 Mio.
La sérialisation CSV est remplacée par le vérificateur dans ce volet ; **ce n’est
pas une importation de 32 Gio dans DuckDB**, ni un débit de bout en bout.
Le second volet conserve de vrais CSV et importe 200 000 événements dans une
collecte, puis rouvre la base et contrôle les lignes, les utilisateurs et les PID.
Les empreintes source sont comparées avant/après.

Le workflow **Linux offline logs** conserve les rapports d’un scénario plus petit
et les résultats des tests. Les contrôles Windows de l’EXE incluent aussi un
corpus Linux : compressions, journal binaire, utmp, audit, texte Unicode, ligne
brute, grille, signet et réouverture d’enquête. Aucune publication de release
n’est déclenchée depuis la PR.

La comparaison indépendante se lance avec
`python -m scripts.benchmarks.linux_journal_oracle --directory DOSSIER --report RAPPORT.json`.
Les fixtures externes sont celles de `fox-it/dissect.target`, révision
`b2378f1504ac9dc87ea511d52bf73fe2b40b545c`, répertoire
`tests/_data/plugins/os/unix/log/journal/`, téléchargées séparément depuis Git LFS.
Elles ne sont pas redistribuées dans Fireblade ; leur provenance et leurs SHA-256
figurent dans le rapport. Les fixtures publiques suivent la licence du dépôt
amont (AGPL-3.0), indépendamment du code MIT de Fireblade.

Les deux fichiers sains totalisent 18 238 entrées : tous leurs champs décodés
correspondent à `journalctl`. Le fichier `unused.journal` altère un lien de tableau
d’entrées : Fireblade signale la corruption ; sa récupération partielle de
252 entrées diffère des 116 entrées renvoyées par `journalctl` dans cet essai.
**Aucune complétude n’est affirmée pour ce fichier corrompu.**

Ces mesures ne constituent pas une qualification universelle des journaux Linux.
Les changements de la PR restent distincts de l’EXE déjà publié et de ses rapports
historiques.
