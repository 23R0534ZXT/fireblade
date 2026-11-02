"""Keep one QApplication alive for the entire test process, including teardown."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QDialog, QMainWindow
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
    application = QApplication.instance()
    existing = set(application.topLevelWidgets()) if application else set()
    yield
    # close() hides a Qt window; its signal/slot cycles can keep it alive.
    # Hidden windows from previous tests otherwise participate in every later
    # theme/palette change and retain their widgets for the entire suite.
    if application:
        application.processEvents()
        for window in application.topLevelWidgets():
            if isinstance(window, (QDialog, QMainWindow)) and window not in existing and not window.isVisible():
                pool = getattr(window, 'pool', None)
                if pool is None or not pool.activeThreadCount():
                    window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
