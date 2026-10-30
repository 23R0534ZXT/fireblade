"""Keep one QApplication alive for the entire test process, including teardown."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication
from fireblade.ui.theme import apply_theme


@pytest.fixture(scope="session", autouse=True)
def qt_application():
    application = QApplication.instance() or QApplication([])
    apply_theme(application)
    yield application
    application.processEvents()


@pytest.fixture(autouse=True)
def isolated_user_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Profil utilisateur"))
