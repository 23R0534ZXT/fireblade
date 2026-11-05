"""Keep one QApplication alive for the entire test process, including teardown."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# The suite and the checks assert on the French labels the code is written with,
# while the application now opens in English. A fresh profile picks its language
# from this variable, so the tests keep a stable, French interface.
os.environ.setdefault("FIREBLADE_LANGUAGE", "fr")

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


@pytest.fixture(scope="session", autouse=True)
def no_blocking_dialog(qt_application):
    """Reject any modal window a test leaves open.

    A dialog in exec() waits for a human who is not there: the suite freezes with
    no output and no CPU use, and the run looks like a hang. The watchdog lives in
    the same thread, so the nested event loop of exec() processes it; the dialog is
    rejected and the test fails on its own assertions instead of never returning.
    """
    from PySide6.QtCore import QTimer

    def reject_stray():
        widget = QApplication.activeModalWidget()
        if isinstance(widget, QDialog):
            print(f"\n[warn] modal window rejected by the test watchdog: {widget.windowTitle()!r}",
                  file=sys.stderr, flush=True)
            widget.reject()

    timer = QTimer(qt_application)
    # Long enough for a test that drives a dialog to fill it in and click OK even on
    # a loaded machine; a dialog nobody drives still costs 15 s instead of forever.
    timer.setInterval(15000)
    timer.timeout.connect(reject_stray)
    timer.start()
    yield
    timer.stop()


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
