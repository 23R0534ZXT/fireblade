import json
import os
from pathlib import Path
import subprocess
import sys

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWidgets import QApplication, QTextBrowser

from fireblade.core.settings import load_settings
from fireblade.runtime import resources
from fireblade.ui.help_dialogs import show_guide, show_licenses, show_tutorial


def test_source_resources_and_user_configuration_priority(tmp_path):
    assert resources.resource_path("docs/guides/UTILISATION.md").is_file()
    assert resources.resource_path("docs/guides/TUTORIEL-COMPLET.md").is_file()
    assert resources.resource_path('docs/guides/CHRONOLOGIE-ET-SAUVEGARDES.md').is_file()
    assert load_settings(resources.default_config()).memory_mb == 128
    from fireblade.runtime.windows_paths import user_directory
    custom = user_directory() / "fireblade.toml"
    custom.parent.mkdir(parents=True)
    custom.write_text("[resources]\nmemory_mb = 128\nthreads = 1\n")
    assert resources.default_config() == custom
    assert load_settings(resources.default_config()).memory_mb == 128


def test_frozen_resources_work_without_adjacent_files(tmp_path, monkeypatch):
    extracted = tmp_path / "Cache Windows" / "_MEI-example"
    bundled = extracted / "resources"
    (bundled / "config").mkdir(parents=True)
    (bundled / "config" / "fireblade.toml").write_text("[resources]\nmemory_mb = 128\n")
    (bundled / "build").mkdir()
    (bundled / "build" / "build-info.json").write_text(json.dumps(dict(packaging="onefile", application="Fireblade")))
    application = tmp_path / "Application été"
    application.mkdir()
    executable = application / "Fireblade.exe"
    executable.write_bytes(b"fake executable for path resolution")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(extracted), raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))
    assert resources.default_config() == bundled / "config" / "fireblade.toml"
    assert load_settings(resources.default_config()).memory_mb == 128
    assert resources.build_info()["packaging"] == "onefile"
    assert sorted(p.name for p in application.iterdir()) == ["Fireblade.exe"]
    legacy = application / "timeline-next.toml"
    legacy.write_text("[resources]\nthreads=1\n")
    assert resources.default_config() == legacy


def test_help_and_license_texts_are_available_without_a_source_browser(qt_application):
    collected, anchors = [], []
    def close_dialog():
        dialog = QApplication.activeModalWidget()
        collected.append(dialog.findChild(QTextBrowser).toPlainText())
        dialog.reject()
    QTimer.singleShot(0, close_dialog)
    show_guide(None)
    def inspect_tutorial():
        dialog = QApplication.activeModalWidget()
        browser = dialog.findChild(QTextBrowser)
        collected.append(browser.toPlainText())
        browser.anchorClicked.emit(QUrl("#parcours-guidé"))
        anchors.append(browser.textCursor().block().text())
        dialog.reject()
    QTimer.singleShot(0, inspect_tutorial)
    show_tutorial(None)
    QTimer.singleShot(0, close_dialog)
    show_licenses(None)
    assert "Regrouper" in collected[0] and "Fireblade.exe" in collected[0]
    assert "Référence de toutes les commandes" in collected[1]
    assert anchors == ["Parcours guidé"]
    assert "MIT License" in collected[2] and "GNU LESSER GENERAL PUBLIC LICENSE" in collected[2]


def test_complete_tutorial_is_available_from_the_help_menu(qt_application):
    from fireblade.ui.app import Window

    window = Window(require_case=False)
    help_menu = next(action.menu() for action in window.menuBar().actions()
                     if action.text().replace("&", "") == "Aide")
    assert any(action.text() == "Tutoriel complet — toutes les fonctionnalités"
               for action in help_menu.actions())
    window.close()


def test_investigation_guide_is_readable_inside_the_application(qt_application):
    from fireblade.ui.help_dialogs import show_investigation_guide
    collected=[]
    def close():
        dialog=QApplication.activeModalWidget()
        collected.append(dialog.findChild(QTextBrowser).toPlainText());dialog.reject()
    QTimer.singleShot(0,close);show_investigation_guide(None)
    assert 'dix dernières versions' in collected[0] and 'Corréler' in collected[0] and 'PDF' in collected[0]


def test_core_import_does_not_load_qt():
    root = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(root / "src")
    result = subprocess.run([sys.executable, "-c", "import sys; from fireblade.core.engine import Case; assert 'PySide6' not in sys.modules"],
                            env=environment, cwd=root, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_ioc_guide_is_readable_inside_application(qt_application):
    from fireblade.ui.help_dialogs import show_ioc_guide
    collected=[]
    def close():
        dialog=QApplication.activeModalWidget()
        collected.append(dialog.findChild(QTextBrowser).toPlainText());dialog.reject()
    QTimer.singleShot(0,close);show_ioc_guide(None)
    assert '50 000' in collected[0] and 'Interrompre' in collected[0] and 'SHA-512' in collected[0]


def test_coverage_guide_is_readable_inside_application(qt_application):
    from fireblade.ui.help_dialogs import show_coverage_guide
    collected=[]
    def close():
        dialog=QApplication.activeModalWidget()
        collected.append(dialog.findChild(QTextBrowser).toPlainText());dialog.reject()
    QTimer.singleShot(0,close);show_coverage_guide(None)
    assert 'SHA-256' in collected[0] and '200 000' in collected[0] and 'jamais collectés' in collected[0]
