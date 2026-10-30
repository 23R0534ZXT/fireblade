import json
import os
from pathlib import Path
import subprocess
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QTextBrowser

from fireblade.core.settings import load_settings
from fireblade.runtime import resources
from fireblade.ui.help_dialogs import show_guide, show_licenses


def test_source_resources_and_user_configuration_priority(tmp_path):
    assert resources.resource_path("docs/guides/UTILISATION.md").is_file()
    assert load_settings(resources.default_config()).memory_mb == 256
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
    collected = []
    def close_dialog():
        dialog = QApplication.activeModalWidget()
        collected.append(dialog.findChild(QTextBrowser).toPlainText())
        dialog.reject()
    QTimer.singleShot(0, close_dialog)
    show_guide(None)
    QTimer.singleShot(0, close_dialog)
    show_licenses(None)
    assert "Regrouper" in collected[0] and "Fireblade.exe" in collected[0]
    assert "MIT License" in collected[1] and "GNU LESSER GENERAL PUBLIC LICENSE" in collected[1]


def test_core_import_does_not_load_qt():
    root = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(root / "src")
    result = subprocess.run([sys.executable, "-c", "import sys; from fireblade.core.engine import Case; assert 'PySide6' not in sys.modules"],
                            env=environment, cwd=root, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
