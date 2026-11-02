# Choisir une collecte du grand pack brut

Les volumes ci-dessous concernent les entrées natives du pack v1, avant les sorties des parseurs. Les origines publiques restent distinctes ; un nom d’origine commun ne garantit pas que tous les fichiers aient été collectés au même instant.

Commencer par `01-Windows/Win10/APTSimulatorVM` ou par une famille à l’intérieur de ce dossier. Pour le scénario synthétique, importer le dossier `catscale_out` d’un des quatre hôtes Linux.

**Importer par origine ou famille, pas tout `01-Windows` en une seule opération** : Fireblade limite les sessions à 1 000 analyses et un fichier peut produire plusieurs analyses. Conserver le mode « un onglet par fichier » pour les premiers essais ; les modes de regroupement constituent un exercice supplémentaire.

| Dossier sous `01-Windows` | Fichiers | Volume brut approximatif | Familles |
|---|---:|---:|---|
| `Win10/APTSimulatorVM` | 226 | 453.2 Mo | Amcache, JumpLists, NTFSArtifacts, Prefetch, Registry, SRUM, WindowsTimeline |
| `Win11/RathbunVM` | 179 | 350.0 Mo | Amcache, LNK, NTFSArtifacts, Prefetch, Registry, SRUM, WindowsTimeline |
| `Win10/RathbunVM` | 238 | 340.5 Mo | Amcache, JumpLists, NTFSArtifacts, Prefetch, Registry, SRUM, WindowsTimeline |
| `Server2022/APTSimulatorVM` | 35 | 251.7 Mo | Amcache, NTFSArtifacts, Registry, SRUM |
| `Win10/BelkasoftCTF_InisderThreat` | 2 | 222.0 Mo | NTFSArtifacts |
| `Win2012R2/StolenSzechuan` | 66 | 214.1 Mo | Amcache, JumpLists, LNK, NTFSArtifacts, Registry |
| `Win11/TheTechHiveScenario` | 202 | 142.6 Mo | EventLogs |
| `Win7/EricZimmerman` | 29 | 137.7 Mo | RecentFileCache, Registry |
| `Win10/BelkasoftCTF_InsiderThreat` | 267 | 74.9 Mo | NTFSArtifacts, Prefetch, Registry, SRUM, WindowsTimeline |
| `Reference-Readers` | 16 | 59.9 Mo | Références des lecteurs |
| `Unknown/tdungan` | 1 | 53.6 Mo | NTFSArtifacts |
| `Win11/SutharPC` | 434 | 48.6 Mo | Prefetch |
| `Win7SP1/RathbunVM` | 40 | 3.9 Mo | Prefetch |
| `Win7/RathbunVM` | 36 | 3.7 Mo | Prefetch |
| `Win81NoUpdate/RathbunVM` | 54 | 2.6 Mo | Prefetch |
| `Win81Update/RathbunVM` | 58 | 2.5 Mo | Prefetch |
| `Win8/RathbunVM` | 43 | 2.2 Mo | Prefetch |
| `Unknown/xw` | 1 | 0.6 Mo | NTFSArtifacts |
| `Win10/Non-attribue` | 428 | 0.5 Mo | LNK |
| `Win11/RathbunVM2` | 32 | 0.4 Mo | Prefetch |
| `WinVista/Non-attribue` | 134 | 0.2 Mo | LNK |
| `Unknown/NIST` | 1 | 0.2 Mo | NTFSArtifacts |
| `Win7/Non-attribue` | 98 | 0.1 Mo | JumpLists, LNK |
| `WinXP/Non-attribue` | 70 | 0.1 Mo | LNK |
| `Win2k3/Non-attribue` | 59 | 0.1 Mo | LNK |
| `Win2012/Non-attribue` | 68 | 0.1 Mo | LNK |
| `Win8.1/Non-attribue` | 33 | 0.0 Mo | LNK |
| `Win8.0/Non-attribue` | 33 | 0.0 Mo | LNK |
| `Win2012R2/EricZimmerman` | 10 | 0.0 Mo | LNK |
| `Win80/Non-attribue` | 1 | 0.0 Mo | JumpLists |
| `Win81/Non-attribue` | 1 | 0.0 Mo | JumpLists |

Le groupe `Reference-Readers` correspond aux références natives du petit pack, avec sa provenance et ses limites. Les dossiers `Non-attribue` ne désignent pas un même hôte : ce sont des exemples sans origine plus précise dans l’arborescence de la source publique.

La qualification du grand pack utilise un buffer DuckDB de **512 Mo**, deux threads et le mode par fichier. Ce budget ne plafonne pas la mémoire totale du programme. Le défaut de l’application est de 256 Mo ; les autres modes et budgets ne sont pas attestés par ce contrôle.

Le ZIP occupe environ un demi-gigaoctet, mais les fichiers bruts extraits dépassent 3 Gio. Les sorties des parseurs, les analyses et leurs temporaires ajoutent de l’espace : commencer par un sous-dossier et suivre l’espace disponible.

[Guide de l’exercice](PACK-BRUT.md) · [Choisir entre découverte, charge CSV et artefacts bruts](JEUX-DE-TEST.md)
