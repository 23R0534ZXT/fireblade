# Notices des composants tiers

Le code de Fireblade est distribué sous la licence MIT conservée dans le fichier LICENSE du dépôt et intégrée au programme.

Le fichier Windows intègre aussi des composants dont les licences restent distinctes : Python, DuckDB, PySide6 Essentials, Shiboken6, Qt, openpyxl, xlrd, et-xmlfile et le chargeur PyInstaller. La construction collecte les notices fournies dans les distributions installées, la licence Python et les métadonnées de version. Le menu Aide → Licences les affiche dans le programme.

Les bibliothèques nécessaires du runtime Microsoft Visual C++ sont aussi intégrées au binaire Windows. Elles restent soumises aux conditions Microsoft et ne sont pas placées sous la licence MIT du projet : https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files

Les roues PySide6 Essentials et Shiboken6 déclarent : `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`. Les textes correspondants et l’exception Qt sont conservés dans `qt/`, à partir du dépôt officiel :

https://github.com/pyside/pyside-setup/tree/dev/LICENSES

Sources et documentation :

- Python : https://www.python.org/downloads/source/
- DuckDB : https://github.com/duckdb/duckdb
- PySide / Shiboken : https://code.qt.io/cgit/pyside/pyside-setup.git/
- Qt : https://code.qt.io/
- xlrd : https://github.com/python-excel/xlrd (licence BSD)
- openpyxl : https://openpyxl.readthedocs.io/
- et-xmlfile : https://et-xmlfile.readthedocs.io/
- PyInstaller : https://pyinstaller.org/en/stable/license.html

La structure du dépôt, les dépendances épinglées et la procédure de construction permettent de reconstruire Fireblade et de modifier les composants utilisés. Voir docs/development/CONTRIBUER.md et scripts/windows/build.py. Le fichier MIT du projet n’a pas vocation à remplacer les licences des dépendances.

Le catalogue des noms de colonnes et types de formats s’appuie sur les déclarations publiques de TLEFilePlugins. Sa notice MIT est conservée dans `TLEFilePlugins-MIT.txt`. La provenance et les limites du catalogue sont décrites dans `docs/development/PLUGINS.md` ; les parseurs C# amont et composants DevExpress ne sont pas embarqués. Le helper de compatibilité est notre propre code C# ; le runtime .NET autonome, sous licence MIT avec notices tierces, est collecté depuis les paquets NuGet lors du build. NumPy est distribué sous BSD-3-Clause avec ses notices ; les licences effectives sont intégrées dans Aide → Licences.

## Pack forensic intégré

Le pack de construction `config/forensic-toolchain.json` fixe les révisions des 13 parseurs EZ Tools et les empreintes des archives Hayabusa 4.3.1 (binaire et sources). Les 70 plugins de registre MIT de RegistryPlugins sont également construits à une révision épinglée pour RECmd. Les parseurs sont construits depuis les projets MIT d’Eric Zimmerman, sans interface propriétaire DevExpress. Lors de la construction, les démarrages Exceptionless sont remplacés par une désactivation de la télémétrie ; le nombre de modifications est enregistré par moteur dans le manifeste du pack. Leurs licences, déclarations des dépendances NuGet et notices du runtime .NET sont copiées dans les ressources légales.

Hayabusa reste un programme séparé, exécuté par sous-processus. Son texte de licence est extrait de l’archive de sources et inclus dans les notices. Les sources correspondant au tag livré sont embarquées dans `forensic-tools/Hayabusa-source.zip`, exportables par le bouton de l’onglet Collecte. Les règles restent distribuées avec leur archive officielle, sans modification automatique à l’exécution. Les empreintes et les liens de sources sont conservés dans les notices et le manifeste du pack.

Le petit EVTX de qualification est un échantillon public DeepBlueCLI distribué dans `Yamato-Security/hayabusa-sample-evtx`, référencé par blob et SHA-256. Il est exclusivement utilisé pour vérifier EvtxECmd et Hayabusa dans l’EXE ; ce n’est pas une donnée utilisateur.
