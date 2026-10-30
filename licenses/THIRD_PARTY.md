# Notices des composants tiers

Le code de Fireblade est distribué sous la licence MIT conservée dans le fichier LICENSE du dépôt et intégrée au programme.

Le fichier Windows intègre aussi des composants dont les licences restent distinctes : Python, DuckDB, PySide6 Essentials, Shiboken6, Qt, openpyxl, et-xmlfile et le chargeur PyInstaller. La construction collecte les notices fournies dans les distributions installées, la licence Python et les métadonnées de version. Le menu Aide → Licences les affiche dans le programme.

Les bibliothèques nécessaires du runtime Microsoft Visual C++ sont aussi intégrées au binaire Windows. Elles restent soumises aux conditions Microsoft et ne sont pas placées sous la licence MIT du projet : https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files

Les roues PySide6 Essentials et Shiboken6 déclarent : `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`. Les textes correspondants et l’exception Qt sont conservés dans `qt/`, à partir du dépôt officiel :

https://github.com/pyside/pyside-setup/tree/dev/LICENSES

Sources et documentation :

- Python : https://www.python.org/downloads/source/
- DuckDB : https://github.com/duckdb/duckdb
- PySide / Shiboken : https://code.qt.io/cgit/pyside/pyside-setup.git/
- Qt : https://code.qt.io/
- openpyxl : https://openpyxl.readthedocs.io/
- et-xmlfile : https://et-xmlfile.readthedocs.io/
- PyInstaller : https://pyinstaller.org/en/stable/license.html

La structure du dépôt, les dépendances épinglées et la procédure de construction permettent de reconstruire Fireblade et de modifier les composants utilisés. Voir docs/development/CONTRIBUER.md et scripts/windows/build.py. Le fichier MIT du projet n’a pas vocation à remplacer les licences des dépendances.
