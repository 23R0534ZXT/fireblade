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
| Syslog traditionnel, timestamps ISO, RFC5424 | Date source, hôte, processus, PID et message ; structured data RFC5424 conservée dans le détail |
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
| lastlog | ABI Linux glibc little-endian de 292 octets ; UID par position, terminal, hôte et date UTC |
| Texte non reconnu, continuation, trace applicative | Une ligne brute avec source, ligne et offset ; pas d’abandon silencieux |
| Autre binaire ou ABI non reconnu | Refus ou erreur explicite, conservation de la source originale |

Rotations gzip, bzip2, XZ/LZMA et Zstandard, y compris en plusieurs couches.
Les TAR sont parcourus en flux sans extraire leurs chemins sur disque.
Les chemins dangereux, liens et membres spéciaux ou sparse sont signalés.
Les champs non projetés restent dans le texte brut ou les champs JSON.
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
fuseau. Les dates audit/Zeek restent des valeurs Unix source, et les dates binaires
utmp/journal sont exprimées en UTC. Les colonnes de la chronologie doivent être
choisies selon ces sémantiques ; un temps monotone n’est pas une date civile.

Les schémas personnalisés, autres ABI utmp/lastlog, fichiers propriétaires et
formats futurs ne peuvent pas être garantis. Les continuations ne sont pas
assemblées automatiquement. La décompression et le décodage d’un journal systemd
ne vérifient pas ses hachages internes ni son scellement cryptographique.
Les octets UTF-8 invalides sont affichés avec des échappements, sans suppression.

Cette extension de code ne constitue pas à elle seule une qualification de tous
les journaux Linux ou de plusieurs dizaines de Gio. Elle doit être distinguée de
la version Windows déjà publiée et de ses rapports historiques.
