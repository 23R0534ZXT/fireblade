# Validation Windows

Le workflow `.github/workflows/windows.yml` est la référence des vérifications automatisées.

## Sources

Les mêmes tests sont exécutés sur Windows natif avec Python 3.11, 3.12 et 3.13. Qt utilise le plugin `windows`, pas `offscreen`. Les rapports JUnit sont publiés dans les artefacts de l’exécution.

Les tests couvrent le moteur, les transactions et annulations, les filtres et tris, la pagination, les groupes, les vues et sessions, XLSX, les règles globales, les notes de sélection et les contraintes de fichiers Windows.

## Exécutable autonome

Après les tests des sources, `scripts/windows/build.py` construit un exécutable PyInstaller `onefile`. `scripts/windows/verify.py` :

1. Copie uniquement ce fichier dans un dossier vide dont le chemin contient espaces et accents.
2. Retire les chemins du Python hôte et des plugins Qt de l’environnement.
3. Utilise un profil utilisateur et un dossier temporaire isolés.
4. Lance la fenêtre Windows réelle et les contrôles intégrés.
5. Vérifie qu’il n’existe toujours que le `.exe` à côté du programme et que son dossier d’extraction temporaire est nettoyé.
6. Enregistre le rapport et le SHA-256 du binaire effectivement exécuté.

Les trente contrôles couvrent notamment le démarrage natif, les ressources intégrées, CSV en lecture seule et Unicode, groupes et précision numérique, export verrouillé puis repris, presse-papiers, réouverture, annulation d’import, couleurs, onglets/sessions, XLS/XLSX, règles globales et annotations collectives. Ils vérifient aussi les fixtures Plaso et layouts officiels, les colonnes dérivées, fuseaux, nanosecondes et le dépliage complet.

La construction ne copie le fichier dans `dist/Fireblade.exe` qu’après succès. Le rapport reste dans `artifacts/windows-single-file.json`, destiné aux développeurs. Il n’est pas requis à côté du programme.

## Reproduire

Depuis la racine du dépôt, sous Windows :

```powershell
python -m scripts.windows.build
python -m scripts.windows.verify --exe dist/Fireblade.exe --report artifacts/verification-manuelle.json
```

Le chemin du rapport doit être nouveau. Pour exécuter directement les contrôles du programme :

```powershell
.\dist\Fireblade.exe --self-test-report "$env:TEMP\fireblade-controle.json"
```

## Limites

Les runners GitHub utilisent leur propre version de Windows, actuellement Windows Server pour les exécutions déjà réalisées. Un job séparé vérifie un partage UNC/SMB temporaire sur le runner et les chemins Unicode de plus de 260 caractères ; il bloque aussi la publication. Le parcours de charge utilise le CSV synthétique de 3 GiB déjà publié, contrôlé par SHA-256, sans régénération.

Ces contrôles automatisés ne remplacent pas les gestes physiques dans l’Explorateur, tous les dialogues natifs, les partages d’entreprise et leurs politiques d’authentification, les sessions prolongées sur Windows 10/11 ou les mesures sur de vrais CSV forensic de plusieurs Go.

Les performances historiques du moteur sont archivées séparément. Aucune comparaison instrumentée avec Timeline Explorer n’a encore établi un gain sur une charge Windows représentative.
