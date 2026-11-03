# Fireblade 0.1.1 — Windows x64 (prototype)

## Nouvelle numérotation

**0.1.1 est la nouvelle numérotation publique du prototype.** Elle reprend les fonctionnalités précédemment numérotées 0.7.0 et ajoute les améliorations ci-dessous. Ce changement de numéro ne retire pas de fonctionnalités. Les anciens rapports et packs conservent leur version, leur commit et leurs empreintes historiques.

## Journaux Linux et collectes

- Import hors ligne de `/var/log/` et des noms de journaux usuels ; sources et offsets conservés, diagnostics explicites pour chaque membre et fichier.
- Syslog traditionnel/RFC5424, audit Linux, Apache/Nginx, JSON Lines, Zeek TSV, W3C extended, kernel et journaux applicatifs horodatés ; projections SSH, sudo, UFW et CEF.
- Lecture native systemd journal standard/compact et Journal Export Format ; utmp/wtmp/btmp et lastlog glibc little-endian ; comptabilité Linux acct_v3 little/big-endian.
- Rotations gzip, bzip2, XZ/LZMA, Zstandard et LZ4, archives TAR/ZIP, textes UTF-16/UTF-32 avec BOM. Lecture en flux, contrôle des troncatures et refus des chemins dangereux, liens et fichiers spéciaux.
- Dates explicitement zonées ou Unix projetées en UTC avec conservation des fractions ; aucune année ni aucun fuseau inventés. Profil de couverture LinuxLogs et colonnes utilisables dans la chronologie.

[Formats, interprétation et limites](https://github.com/23R0534ZXT/fireblade/blob/main/docs/guides/JOURNAUX-LINUX.md).

## Environnement d’investigation conservé

Cases persistants, sauvegardes et archives portables vérifiées ; 13 EZ Tools et 70 plugins RECmd intégrés ; Shellbags, WebCache, CatScale ; Hayabusa avec contexte EVTX ; chronologie, corrélations, chasse IOC, annotations et rapports HTML/PDF ; exports CSV/XLSX relus et vérifiés.

## Qualification et version du binaire

La publication attend les contrôles du tag `v0.1.1` : tests Windows Python 3.11/3.12/3.13, EXE autonome, lecteurs intégrés, chemins UNC/longs, huit configurations visuelles, 320 analyses et scénario interactif sur plus de 3 Gio. Les versions de fichier et de produit Windows doivent correspondre à **0.1.1**.

Les mesures préalables de l’extension Linux ont vérifié une source unique de **32 Gio décompressés**, avec contrôle des enregistrements et de leur empreinte en flux (sans sérialisation CSV ni import DuckDB pour ce volet), puis **1 000 000 d’événements réellement importés et relus**. Deux journaux systemd publics sains ont été comparés à `journalctl` : 18 238 entrées avec tous les champs identiques. Les écarts sur le fichier corrompu sont explicités dans le guide.

## Limites

Prototype non signé. Les essais automatisés ne qualifient pas tous les postes, tous les formats propriétaires ou chaque fichier endommagé. Les binaires inconnus, erreurs et lectures brutes restent signalés ; les hachages/scellements internes systemd ne sont pas vérifiés. Les archives CatScale conservent leur lecteur et leurs limites. Les lecteurs Linux ont des bornes explicites et les limites générales du nombre d’analyses restent applicables. Le budget DuckDB ne plafonne pas la RAM de tous les composants.

## Télécharger et donner un retour

Télécharger **Fireblade.exe** et le lancer sous Windows x64. Python, Excel et une installation préalable de .NET ne sont pas nécessaires. Interface et guides en français.

[Pack de découverte](https://github.com/23R0534ZXT/fireblade/releases/tag/test-pack-v1) · [Grand pack BRUT](https://github.com/23R0534ZXT/fireblade/releases/tag/raw-artifacts-v1) · [Retours des testeurs](https://github.com/23R0534ZXT/fireblade/issues/6) · [Signaler un problème](https://github.com/23R0534ZXT/fireblade/issues/new/choose)

Le workflow ajoute le commit qualifié et le SHA-256 exact de l’EXE à ces notes lors de la publication.
