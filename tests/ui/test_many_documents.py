"""Exercise real databases, tab navigation, workspace search and session references."""
import time

from PySide6.QtCore import QCoreApplication, QEvent

from fireblade.core.engine import Case
from fireblade.ui.app import Window
from fireblade.ui.cross_search import WorkspaceSearch
from fireblade.ui.workspace import read_session, write_session


def test_320_real_analyses_keep_navigation_search_and_session(qt_application, tmp_path):
    window = Window(require_case=False)
    errors = []
    window.error = errors.append
    window.resize(800, 600)
    window.tabs.set_multiline(True)
    window.show()

    def settle():
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            qt_application.processEvents()
            if not window.jobs and not window.pool.activeThreadCount() and (window.model is None or not window.model.jobs) and not window.tabs.pending:
                QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
                return
            time.sleep(.005)
        raise AssertionError('Workspace work did not settle')

    try:
        for index in range(320):
            source = tmp_path / f'case-{index:03}.csv'
            source.write_text(f'Marker,User\ncase-{index:03},alice\n', encoding='utf-8')
            case = Case(tmp_path / f'case-{index:03}.timeline', settings=window.settings)
            case.import_csv(source)
            settle()
            window.detach()
            window.attach(case)
            settle()
        assert len(window.documents) == window.tabs.count() == 320
        assert window.tabs.height() <= 3 * max(bar.sizeHint().height() for bar in window.tabs.rows)
        for index in (0, 159, 319):
            window.tabs.setCurrentIndex(index)
            settle()
            assert window.active_document == index
            assert window.case.info['path'] == str(tmp_path / f'case-{index:03}.csv')
            assert window.model.data(window.model.index(0, 1)) == f'case-{index:03}'
        hits = WorkspaceSearch(window.documents, window.settings, window.case).find('alice')
        assert len(hits) == 320
        assert all(hit.count == 1 and not hit.error for hit in hits)
        window.remember_active()
        session = tmp_path / 'all.fireblade-session'
        write_session(session, window.documents, window.active_document)
        snapshots, active = read_session(session)
        assert active == 319 and len(snapshots) == 320
        assert [snapshot.path for snapshot in snapshots] == [snapshot.path for snapshot in window.documents]
        assert not errors
    finally:
        settle()
        window.close()
