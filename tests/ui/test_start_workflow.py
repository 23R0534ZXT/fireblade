import threading
import time

from PySide6.QtCore import Qt

from fireblade.core.disk import DiskCollection
from fireblade.ui.app import Window
from fireblade.ui.startup import StartupAnimation


def until(app, predicate):
    deadline = time.monotonic()+15
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate(): return
        # QTest.qWait can retain the Python GIL on Windows. Let QRunnable
        # callbacks execute Python between GUI event batches.
        time.sleep(.005)
    import faulthandler
    faulthandler.dump_traceback()
    raise AssertionError('Timed out')


def idle(window):
    return (not window.busy and not window.jobs and not window.pool.activeThreadCount()
            and not (window.model and window.model.jobs))


def test_case_gate_and_two_choices(qt_application, tmp_path):
    window = Window(investigation_root=tmp_path/'cases')
    try:
        assert not window.workbench.isTabEnabled(0)
        window.open_path(tmp_path/'missing.csv')
        assert not window.documents
        assert not window.can_open_file()
        assert window.can_open_file(allow_without_case=True)
        data = window.create_investigation('First case')
        assert data and window.workbench.isTabEnabled(0)
        assert window.welcome_title.text() == 'First case'
        assert window.close_investigation()
        assert not window.workbench.isTabEnabled(0)
    finally: window.close()


def test_progressive_disk_keeps_workspace_interactive(qt_application, tmp_path, monkeypatch):
    root = tmp_path/'source'; (root/'var/log').mkdir(parents=True)
    (root/'var/log/auth.log').write_text('2026-11-03T12:00:00Z host sshd[1]: test\n')
    release = threading.Event(); reached = threading.Event()
    original = DiskCollection.publish_results
    def publish(self, start, entry):
        original(self, start, entry)
        reached.set()
        release.wait(30)
    monkeypatch.setattr(DiskCollection, 'publish_results', publish)
    window = Window(investigation_root=tmp_path/'cases', require_case=True)
    errors = []; window.error = errors.append
    case = window.create_investigation('Disk case')
    try:
        assert window.start_disk_analysis(root)
        assert window.workbench.currentIndex() == 0
        until(qt_application, lambda: reached.is_set() and window.case is not None and idle(window))
        assert window.disk_job is not None
        assert window.centralWidget().isEnabled()
        assert window.documents and window.disk_progress.maximum() == 0
        assert not window.close_investigation()
        window.search.setText('host')
        window.apply()
        until(qt_application, lambda: idle(window))
        assert window.case is not None
        texts = [item.text(0) for item in window.navigator.items()]
        assert 'volume' in texts and 'var' in texts and 'log' in texts
        window.set_navigation_option('navigation_position', 'right')
        assert window.workspace_splitter.indexOf(window.navigator) == 1
        window.set_navigation_option('navigation_grouping', 'flat')
        assert not any(item.text(0) == 'var' for item in window.navigator.items())
        release.set()
        until(qt_application, lambda: window.disk_job is None and not window.disk_pool.activeThreadCount() and not window._disk_pending and idle(window))
        assert not errors
        assert window.close()
        restarted = Window(investigation_root=tmp_path/'cases', require_case=True)
        try:
            assert restarted.preferences.navigation_position == 'right'
            assert restarted.open_investigation(case['id'])
            until(qt_application, lambda: idle(restarted))
            restarted.set_navigation_option('navigation_grouping', 'folders')
            assert any(item.text(0) == 'var' for item in restarted.navigator.items())
        finally: restarted.close()
    finally:
        release.set()
        until(qt_application, lambda: window.disk_job is None and not window.disk_pool.activeThreadCount() and not window._disk_pending and idle(window))
        window.close()


def test_animation_finishes_without_sleeping_ui(qt_application):
    splash = StartupAnimation(); finished = []
    assert splash.animation.duration() == 10000
    assert splash.movie.isValid() and splash.movie.frameCount() >= 190
    splash.finished.connect(lambda: finished.append(True))
    splash.show(); splash.animation.start()
    until(qt_application, lambda: bool(finished))
    assert splash.phase == 1.0
    assert not splash.grab().isNull()
    splash.close()


def test_disk_completion_waits_for_an_active_grid_job(qt_application, tmp_path):
    root = tmp_path/'source'; (root/'var/log').mkdir(parents=True)
    (root/'var/log/auth.log').write_text('2026-11-03T12:00:00Z host sshd[1]: test\n')
    window = Window(investigation_root=tmp_path/'cases')
    errors = []; window.error = errors.append
    window.create_investigation('Concurrent finish')
    release = threading.Event(); entered = threading.Event()
    def grid_work():
        entered.set(); release.wait(10)
    try:
        assert window.start_disk_analysis(root)
        window.run(grid_work, lambda _: None, exclusive=True)
        until(qt_application, lambda: entered.is_set() and not window.disk_pool.activeThreadCount())
        assert window.busy and window.disk_job is not None
        assert not window.centralWidget().isEnabled()
        release.set()
        until(qt_application, lambda: window.disk_job is None and not window._disk_pending and idle(window))
        assert window.documents and window.centralWidget().isEnabled()
        assert not errors
    finally:
        release.set()
        until(qt_application, lambda: window.disk_job is None and not window.disk_pool.activeThreadCount() and idle(window))
        window.close()


def test_failed_initial_case_save_does_not_start_an_orphan_job(qt_application, tmp_path, monkeypatch):
    root = tmp_path/'source'; root.mkdir()
    window = Window(investigation_root=tmp_path/'cases')
    window.create_investigation('Save failure')
    try:
        with monkeypatch.context() as patch:
            patch.setattr(window, 'persist_investigation', lambda *args, **kwargs: False)
            assert not window.start_disk_analysis(root)
        assert window.disk_job is None and not window.disk_pool.activeThreadCount()
        assert window.investigation_collections == []
        assert not list(window.investigation_data_directory('Disques').iterdir())
    finally:
        window.close()


def test_cancelling_before_worker_start_saves_a_cancelled_collection(qt_application, tmp_path, monkeypatch):
    import json
    root = tmp_path/'source'; root.mkdir()
    window = Window(investigation_root=tmp_path/'cases')
    window.create_investigation('Early cancellation')
    queued = []
    try:
        with monkeypatch.context() as patch:
            patch.setattr(window.disk_pool, 'start', queued.append)
            assert window.start_disk_analysis(root)
        output = window.disk_collection.output
        window.cancel_disk()
        window.disk_pool.start(queued[0])
        until(qt_application, lambda: window.disk_job is None and not window.disk_pool.activeThreadCount())
        report = json.loads((output/'collection.json').read_text())
        assert report['status'] == 'cancelled' and not report['documents']
        assert 'Interrompu' in window.disk_label.text()
    finally:
        window.close()


def test_hidden_details_preference_is_restored(qt_application, tmp_path):
    window = Window(investigation_root=tmp_path/'cases')
    window.details_action.trigger()
    assert not window.preferences.workspace_details_visible
    assert window.details.isHidden()
    assert window.close()
    restarted = Window(investigation_root=tmp_path/'cases')
    try:
        assert not restarted.details_action.isChecked()
        assert restarted.details.isHidden()
    finally:
        restarted.close()


def test_rejected_source_does_not_create_disk_work_directory(qt_application, tmp_path):
    root = tmp_path/'source'; root.mkdir()
    window = Window(investigation_root=root/'cases')
    errors = []; window.error = errors.append
    data = window.create_investigation('Destination inside source')
    destination = window.investigation_library.folder(data['id'])/'Disques'
    try:
        assert not destination.exists()
        assert not window.start_disk_analysis(root)
        assert not destination.exists()
        assert errors and window.disk_job is None
    finally:
        window.close()


def test_navigation_accepts_windows_and_portable_origin_paths(qt_application, tmp_path):
    from fireblade.core.models import AnalysisSnapshot, View
    from fireblade.ui.navigation import AnalysisNavigator
    document = AnalysisSnapshot(str(tmp_path/'analysis.timeline'), {'path': str(tmp_path/'result.csv')}, View(), b'')
    navigator = AnalysisNavigator()
    try:
        for relative in ('var/log/auth.log', r'var\log\auth.log'):
            navigator.refresh([document], 0, [], origins={document.path: dict(
                partition='partition-1', relative=relative, artifact='Journaux Linux')}, grouping='folders')
            labels = {item.text(0) for item in navigator.items()}
            assert {'partition-1', 'var', 'log', 'auth.log · Journaux Linux'} <= labels
    finally:
        navigator.close()
        navigator.deleteLater()
