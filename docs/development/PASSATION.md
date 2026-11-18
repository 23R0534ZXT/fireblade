# Passation — Fireblade, 18 novembre 2026 (nuit)

Document de reprise. Il dit où en est le dépôt, ce qui a été construit, ce qui est
mesuré, ce qui reste ouvert, et comment vérifier. Le détail des procédures vit dans le
skill `fireblade-verification`.

## 1. Où vit le travail

**Tout se fait depuis Proxmox, sur la VM Windows 11** `fb@192.168.1.80` (VM 300,
`win11-dfir`, 4 cœurs / 8 Go, `C:\Users\fb\dev\fireblade`). La tour n'est plus utilisée.
Git de la VM : `C:\Users\fb\tools\git\cmd\git.exe`. Interpréteur :
`C:\Users\fb\dev\fireblade\.venv\Scripts\python.exe` (3.12.10).

## 2. État à l'instant

| Élément | État |
|---|---|
| Branche | `hermes/0.5.0-assistant`, trois commits, **pas poussée** |
| Version | 0.5.0 (prototype assumé) |
| Porte | verte sur la VM : **1527 passés, 28 ignorés, 954 s** (`vm_gate.ps1`) |
| Modèle local | moteur llama.cpp `b12483` + MiniCPM5-2B Q4_K_M (1 561 318 368 octets, SHA-256 `ec2d5801…602fd`) |
| Recette | `s0`, `s1` (972 s, 214 analyses), `s2`, `s4` à `s9` vertes ; `s10_assistant.py` (9 étapes) et `s11_strain.py` (8 étapes) vertes ; captures `C:\fireblade-test\shots\S10-*` et `S11-*` |
| Non concluant | `s3_tools.py` : se bloque sur la boîte « sources and dates » **et le fait aussi sur `main`** — défaut du harnais sur cette VM, pas une régression 0.5.0 |
| Mesure de qualité | `vm_quality.py` : 6 constats × 2 formes de prompt, résultats dans `C:\Users\fb\quality.json` |

## 3. Ce que contient la 0.5.0

- Onglet **Hayabusa + AI** : constats regroupés **en SQL (DuckDB)** par règle / hôte /
  rafale, puis rassemblés en fenêtres horaires ; repli mémoire si le SQL échoue, avec la
  raison affichée.
- **Trois vues peintes, une seule palette** : le jour est un **histogramme polaire** (un
  rayon par tranche de dix minutes, longueur = alertes, couleur = gravité la plus haute),
  la carte de chaleur donne une ligne par règle dans le temps, la chaîne montre les
  événements du constat et les liens que l'assistant affirme. Les trois suivent le thème
  clair ou sombre de la fenêtre.
- **Assistant local optionnel** : téléchargement du moteur et des poids (une fois),
  manifeste `assistant.json`, vérification mémoire / empreinte avant démarrage.
- **Bouton « Explain this finding »** et **chat** : paquet de preuve borné (40 événements
  numérotés), sortie JSON (résumé, faits cités, liens, manques), **vérifiée** avant
  affichage — un fait sans événement, ou citant un événement inconnu, est écarté avec sa
  raison ; un lien n'est gardé que si ses deux extrémités existent.
- **Liens dessinés** dans la vue chaîne, fléchés et numérotés.
- **Une seule question à la fois** : le temps écoulé s'affiche, une seconde demande est
  refusée avec une phrase visible au lieu d'être mise en file. Une réponse reste attachée
  à son constat et revient quand on y retourne.
- **Moteur ressuscité une fois** : sur 8 Go, le serveur llama.cpp est mort en pleine
  réponse (`ConnectionRefusedError` 10061 ensuite) ; l'appel est rejoué sur un moteur neuf,
  une seule fois, puis l'erreur remonte.
- Mesuré sur la VM (4 cœurs, sans GPU) : **25 à 45 s** par explication (moyenne 28 s sur
  six constats), **29 s** pour une question de suivi ; le moteur reste chargé entre deux
  questions. Une réponse coupée au budget de jetons est annoncée comme coupée.

## 4. Décisions prises, à ne pas rouvrir sans raison

- **Le modèle ne décide de rien** : il écrit de la prose sur un paquet de preuve, et
  Fireblade vérifie chaque citation. Comptages, tris et jointures restent du code.
- **Réflexion du modèle coupée** (`enable_thinking=False`) : en mode « thinking », ce
  modèle écrit dans un champ séparé et rend une réponse vide ; la latence triple pour
  rien. Constaté à la mesure, pas supposé.
- **Le prompt dit quels numéros existent** (« les numéros valides vont de 1 à N ») : les
  faits conservés passent de 1,3 à 1,5 par constat et les rejets diminuent de moitié.
  Un exemple travaillé dans le prompt **dégrade** la réponse (1,3 fait, 0,5 lien contre
  1,5 et 1,0) : il n'est pas utilisé. Les deux formes restent dans `explain.py` pour être
  remesurées si le modèle change.
- **Une dépendance ajoutée** : `pytz`, exigée par DuckDB pour convertir un `TIMESTAMPTZ`.
  Sans elle, tout regroupement temporel échoue sur « Required module 'pytz' failed to
  import ».
- **Le moteur est téléchargé, jamais embarqué** : binaire llama.cpp CPU épinglé par tag,
  poids vérifiés par SHA-256. Conséquence assumée : l'installation du modèle demande
  Internet une fois, puis tout est hors ligne.
- **Le runtime Visual C++ est un prérequis** de llama.cpp : sur une VM Windows 11 nue le
  binaire meurt en `STATUS_DLL_NOT_FOUND` (0xC0000135). `vc_redist.x64.exe` est installé
  sur la VM de recette ; un installateur devra le prévoir.
- Le regroupement par défaut est le SQL ; la version Python reste pour les tests et le
  repli, et un test vérifie que les deux produisent les mêmes constats.

## 5. Pièges rencontrés cette nuit

- **Le disque de la VM s'est rempli** (96 Go, 0 libre) : les deux cas du test 10 Gio pèsent
  20 Go chacun dans `%LOCALAPPDATA%\Fireblade\Cases`. Symptômes trompeurs : une boîte
  « No space left on device », puis une section qui se bloque, puis un abandon Python dont
  la trace finit en `object refcount : 3`. Nettoyage des cas, `Get-PSDrive C` avant chaque
  recette.
- Windows Update a **redémarré la VM deux fois** pendant les tests (`id 1074`,
  TrustedInstaller). Politique posée : `NoAutoRebootWithLoggedOnUsers=1`.
- `scp` vers la VM passe par **PowerShell** : `&&`, `;` et les variables `%VAR%` de cmd
  n'y existent pas ; écrire des `.ps1` et les lancer avec `-File`.
- `PowerShell -File` **ne découpe pas** les tableaux : `-Files a,b` arrive en une seule
  chaîne. Le plan de build passe donc par un `build.json`.
- **Un onglet impose sa largeur minimale à toute la fenêtre** : une phrase de résumé dans
  un `QLabel` a fait monter la largeur minimale à 1252 px et cassé deux tests 1024×600.
  Les libellés longs passent par `shrinkable()` (politique `Ignored`, texte complet en
  infobulle) ; les cartes gardent une hauteur minimale basse (120 px).
- La hauteur minimale des vues avait aussi dépassé 600 px : garder 120 px, pas 190.
- Un `TIMESTAMPTZ` DuckDB exige `pytz` (voir §4) ; un `UNION ALL` refuse un `ORDER BY`
  avant la seconde branche.
- `assistant.json` écrit par PowerShell porte un **BOM** : le lire en `utf-8-sig`, sinon
  « installé » devient « désactivé ».
- Le harnais de recette utilise son propre `LOCALAPPDATA` : le modèle doit être copié dans
  `C:\fireblade-test\profile\Fireblade\Assistant` (`vm_seed_profile.ps1`).
- `powershell ... *> log` transforme **tout message Qt sur stderr en erreur PowerShell** :
  le code de sortie devient 1 alors que la section a réussi. Les lanceurs passent par
  `Start-Process` avec `-RedirectStandardError` et lisent `$process.ExitCode`.
- Un `Start-Process` détaché meurt avec la session ssh : les longues suites se lancent
  depuis le poste Proxmox, section par section (`tools/recette.sh`).
- `Start-Process -Wait` **attend aussi les handles hérités** : avec llama-server encore
  vivant, la section imprime `SECTION_DONE` et le lanceur ne rend jamais la main. Utiliser
  `WaitForExit(ms)` et retomber sur la présence de `SECTION_DONE` dans le journal.

## 6. Vérifier

```powershell
# sur la VM, dans C:\Users\fb\dev\fireblade
powershell -File C:\Users\fb\vm_gate.ps1                    # ~16 min, doit finir TOUT EST VERT
powershell -File C:\Users\fb\vm_section.ps1 -Name s10_assistant
powershell -File C:\Users\fb\vm_section.ps1 -Name s11_strain
```

Recette complète : `tools/recette.sh` depuis Proxmox enchaîne `s0` à `s11` et écrit
`recette-report.txt`. Journal détaillé et captures : `C:\fireblade-test\harness\journal.json`,
`C:\fireblade-test\shots\`.

Qualité de l'assistant : `powershell -File C:\Users\fb\vm_quality_run.ps1` puis relire
`C:\Users\fb\quality.json` (validité JSON, faits conservés / rendus, liens, secondes).

## 7. Ce qui reste ouvert

1. **Qualité du modèle** : MiniCPM5-2B donne un résumé utile mais pauvre (1 à 2 faits par
   constat) ; c'est une limite du modèle, pas du garde-fou. Un modèle plus gros tiendrait
   sur la même interface.
2. **Enquête multi-étapes** : l'assistant explique un constat, il ne conduit pas
   l'analyse.
3. **Paquet de preuve** borné à 40 événements ; au-delà, le nombre non lu est écrit.
4. **`vc_redist`** à intégrer proprement au programme d'installation.
5. Sujets 0.4.2 toujours ouverts : guides en français, `docs/validation` embarqué dans
   l'exe, résidu de traduction « exports ».
