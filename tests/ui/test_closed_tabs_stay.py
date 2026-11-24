"""A closed tab keeps its analysis in the case, listed by the navigation tree.

The complaint: closing an artifact grid made the file disappear from the tree, so the
analyst could not get it back without re-importing. Closing a tab now only closes the tab.
"""

import time

from PySide6.QtCore import Qt

from fireblade.core.models import AnalysisSnapshot, View
from fireblade.ui.navigation import AnalysisNavigator


def snapshot(tmp_path, name):
    path = tmp_path / f"{name}.timeline"
    path.touch()
    return AnalysisSnapshot(str(path), {"path": str(tmp_path / f"{name}.csv")}, View(), b"")


def test_a_closed_analysis_stays_in_the_tree(qt_application, tmp_path):
    opened = snapshot(tmp_path, "opened")
    closed = snapshot(tmp_path, "closed")
    navigator = AnalysisNavigator()
    navigator.refresh([opened], 0, [], {}, {}, "families", [closed])
    try:
        titles = [item.text(0) for item in navigator.items()]
        assert any("closed" in title for title in titles), titles
        assert any("opened" in title for title in titles), titles
    finally:
        navigator.deleteLater()


def test_activating_a_closed_analysis_asks_to_reopen_it(qt_application, tmp_path):
    opened = snapshot(tmp_path, "opened")
    closed = snapshot(tmp_path, "closed")
    navigator = AnalysisNavigator()
    navigator.refresh([opened], 0, [], {}, {}, "families", [closed])
    reopened, activated = [], []
    navigator.reopened.connect(reopened.append)
    navigator.activated.connect(activated.append)
    try:
        item = next(item for item in navigator.items() if item.data(0, Qt.UserRole + 2) == "closed")
        navigator.activate(item)
        navigator.activate(
            next(item for item in navigator.items() if item.data(0, Qt.UserRole) == 0)
        )
        assert reopened == [closed.path]
        assert activated == [0]
    finally:
        navigator.deleteLater()


def _real_analysis(tmp_path, name):
    from fireblade.core.engine import Case

    source = tmp_path / f"{name}.csv"
    source.write_text("User,Action\nalice,login\n", encoding="utf-8")
    case = Case(tmp_path / f"{name}.timeline")
    try:
        info = case.import_csv(source)
    finally:
        case.close()
    return AnalysisSnapshot(str(case.path), info, View(), b"")


def test_closing_a_tab_moves_it_out_of_the_tabs_but_not_out_of_the_case(qt_application, tmp_path):
    from fireblade.ui.app import Window

    first, second = _real_analysis(tmp_path, "first"), _real_analysis(tmp_path, "second")
    window = Window(investigation_root=tmp_path / "cases")
    try:
        window.create_investigation("Closed tabs")
        window.install_session_snapshots([first, second], 0)
        assert [doc.path for doc in window.documents] == [first.path, second.path]
        # The window refuses to close a tab while it is still loading rows.
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and not window.can_open_file():
            qt_application.processEvents()
            time.sleep(0.05)
        assert window.can_open_file()
        window.close_document(1)
        assert [doc.path for doc in window.documents] == [first.path]
        assert [doc.path for doc in window.closed_documents] == [second.path]
        while time.monotonic() < deadline and not window.can_open_file():
            qt_application.processEvents()
            time.sleep(0.05)
        assert window.reopen_closed_analysis(second.path)
        assert [doc.path for doc in window.documents] == [first.path, second.path]
        assert window.closed_documents == []
    finally:
        window.close()
