import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import time
from PySide6.QtCore import QModelIndex, QThreadPool
from PySide6.QtWidgets import QApplication

from timeline_next.app import Window
from timeline_next.grid import GridModel
from timeline_next.engine import Case, View
from timeline_next.settings import Settings
from timeline_next.workers import Job


def wait(app, predicate):
    deadline = time.monotonic() + 10
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.005)
    assert predicate()


def test_async_model_nested_groups_and_window(tmp_path):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / 'ui.csv'
    source.write_text('Artifact,User,ID\n' + ''.join(f'MFT,alice,{i:06d}\n' for i in range(1300)))
    case = Case(tmp_path / 'ui.timeline')
    case.import_csv(source)
    pool = QThreadPool()
    pool.setMaxThreadCount(1)
    model = GridModel(case, pool)
    errors = []
    model.error.connect(errors.append)
    model.reset(View(groups=[0, 1]))
    wait(app, lambda: model.rowCount() == 1)
    group = model.index(0, 0)
    model.fetchMore(group)
    wait(app, lambda: model.rowCount(group) == 1)
    subgroup = model.index(0, 0, group)
    model.fetchMore(subgroup)
    wait(app, lambda: model.rowCount(subgroup) == 250)
    assert model.parent(model.index(0, 1, subgroup)) == subgroup
    assert model.data(model.index(0, 3, subgroup)) == '000000'
    # Fetch enough pages to exercise bounded leaf-window replacement.
    for expected_offset in range(250, 1251, 250):
        model.fetchMore(subgroup)
        wait(app, lambda: not model.node(subgroup).loading)
    assert model.node(subgroup).offset == 1000
    assert model.rowCount(subgroup) == 300
    assert not model.canFetchMore(subgroup)
    assert not model.node(subgroup).more
    model.previous(subgroup)
    wait(app, lambda: not model.node(subgroup).loading)
    assert model.node(subgroup).offset == 0
    assert model.data(model.index(0, 3, subgroup)) == '000000'
    assert not errors
    pool.waitForDone()
    window = Window()
    window.attach(case)
    window.show()
    wait(app, lambda: window.model.rowCount() > 0 and not window.jobs and not window.model.jobs)
    window.tree.setCurrentIndex(window.model.index(0, 0))
    app.processEvents()
    assert '000000' in window.details.toPlainText()
    window.view.highlight = 'alice'
    window.apply()
    wait(app, lambda: not window.jobs and not window.model.jobs)
    window.copy_rows()
    assert 'Artifact' in QApplication.clipboard().text()
    window.pool.waitForDone()
    assert window.close()


def test_group_window_and_collapse_release_cached_rows(tmp_path):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / 'groups.csv'
    source.write_text('Artifact,ID\n' + ''.join(f'Group{i:03d},{i}\n' for i in range(80)))
    case = Case(tmp_path / 'groups.timeline', settings=Settings(page_size=25, max_loaded_rows=50))
    case.import_csv(source)
    pool = QThreadPool()
    pool.setMaxThreadCount(1)
    model = GridModel(case, pool)
    model.reset(View(groups=[0]))
    wait(app, lambda: not model.jobs)
    first = model.index(0, 0)
    node = model.node(first)
    model.fetchMore(first)
    wait(app, lambda: not model.jobs)
    assert model.rowCount(first) == 1
    model.unload(first)
    assert model.rowCount(first) == 0
    assert node.more
    model.fetchMore(first)
    wait(app, lambda: not model.jobs)
    assert model.rowCount(first) == 1
    for _ in range(2):
        model.fetchMore()
        wait(app, lambda: not model.jobs)
    assert model.root.offset == 50
    assert model.rowCount() == 25
    assert not model.attached(node)
    model.previous()
    wait(app, lambda: not model.jobs)
    assert model.root.offset == 0
    assert model.data(model.index(0, 0)).startswith('Artifact : Group000')
    pool.waitForDone()
    case.close()


def test_collapse_and_reset_skip_obsolete_queued_queries(tmp_path):
    import threading
    app = QApplication.instance() or QApplication([])
    source = tmp_path / 'pending.csv'
    source.write_text('Artifact,ID\nMFT,0001\nEVTX,0002\n')
    case = Case(tmp_path / 'pending.timeline')
    case.import_csv(source)
    pool = QThreadPool()
    pool.setMaxThreadCount(1)
    model = GridModel(case, pool)
    errors, calls = [], []
    model.error.connect(errors.append)
    page = case.page
    def tracked(*args, **kwargs):
        calls.append(args)
        return page(*args, **kwargs)
    case.page = tracked
    model.reset(View(groups=[0]))
    wait(app, lambda: not model.jobs)
    calls.clear()
    gate, started = threading.Event(), threading.Event()
    def block():
        started.set()
        gate.wait(5)
    blocker = Job(block)
    pool.start(blocker)
    assert started.wait(1)
    group = model.index(0, 0)
    model.fetchMore(group)
    model.unload(group)
    model.fetchMore(group)
    # Also invalidate that replacement query before it reaches the database.
    model.reset(View(search='MFT'))
    gate.set()
    wait(app, lambda: not model.jobs)
    assert len(calls) == 1
    assert model.rowCount() == 1
    assert model.data(model.index(0, 1)) == 'MFT'
    assert not errors
    pool.waitForDone()
    case.close()
