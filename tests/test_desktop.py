import hashlib
import os
from pathlib import Path
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QLineEdit

from timeline_next.app import Window
from timeline_next.dialogs import ImportDialog
from timeline_next.engine import Case
from timeline_next.menus import cell_menu, header_menu
from timeline_next.models import Filter, View
from timeline_next.theme import apply_theme


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    apply_theme(instance)
    return instance


def settle(app, window):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        app.processEvents()
        if not window.jobs and not window.pool.activeThreadCount() and (window.model is None or not window.model.jobs):
            return
        time.sleep(.005)
    pytest.fail("The desktop did not finish its background operations")


@pytest.fixture
def window(app, tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("Artifact,User,ID\nMFT,alice,001\nEVTX,bob,10\nMFT,alice,2\nEVTX,,3\n", encoding="utf-8")
    case = Case(tmp_path / "source.timeline")
    case.import_csv(source)
    w = Window()
    errors = []
    w.error = errors.append
    w.attach(case)
    w.show()
    settle(app, w)
    yield w
    settle(app, w)
    assert not errors
    assert w.close()


def trigger(menu, text):
    item = next(action for action in menu.actions() if action.text() == text)
    item.trigger()
    menu.deleteLater()


def test_header_actions_sort_group_and_hide(app, window):
    assert header_menu(window, 0) is None
    trigger(header_menu(window, 3), "Trier par ordre décroissant")
    settle(app, window)
    assert [window.model.node(window.model.index(i, 0)).values[3] for i in range(4)] == ["3", "2", "10", "001"]
    menu = header_menu(window, 3)
    types = next(action.menu() for action in menu.actions() if action.text() == "Type de tri")
    next(action for action in types.actions() if action.text() == "Nombre").trigger()
    menu.deleteLater()
    settle(app, window)
    assert [window.model.node(window.model.index(i, 0)).values[3] for i in range(4)] == ["10", "3", "2", "001"]
    trigger(header_menu(window, 1), "Grouper par cette colonne")
    settle(app, window)
    assert window.view.groups == [0]
    trigger(header_menu(window, 2), "Ajouter au groupement")
    settle(app, window)
    assert window.view.groups == [0, 1]
    trigger(header_menu(window, 1), "Retirer du groupement")
    settle(app, window)
    assert window.view.groups == [1]
    trigger(header_menu(window, 3), "Masquer cette colonne")
    assert window.tree.isColumnHidden(3)


def test_cell_quick_filters_include_nulls_on_exclusion(app, window):
    index = window.model.index(0, 2)
    trigger(cell_menu(window, index), "Copier la valeur")
    assert QApplication.clipboard().text() == "alice"
    trigger(cell_menu(window, index), "Exclure cette valeur")
    settle(app, window)
    assert window.case.count(window.view) == 2  # bob and the empty value
    assert window.view.filters == [Filter(1, "ne", "alice")]
    window.reset()
    settle(app, window)
    trigger(cell_menu(window, window.model.index(0, 2)), "Filtrer sur cette valeur")
    settle(app, window)
    assert window.case.count(window.view) == 2
    window.reset()
    settle(app, window)
    trigger(cell_menu(window, window.model.index(3, 2)), "Filtrer sur cette valeur")
    settle(app, window)
    assert window.case.count(window.view) == 1
    assert window.view.filters == [Filter(1, "empty")]


def test_header_filter_prefills_column_and_filters_rows(app, window, monkeypatch):
    def accept_filter(dialog):
        column, operator = dialog.findChildren(QComboBox)
        assert column.currentText() == "User"
        assert operator.currentData() == "contains"
        dialog.findChild(QLineEdit).setText("bob")
        return QDialog.Accepted
    monkeypatch.setattr(QDialog, "exec", accept_filter)
    trigger(header_menu(window, 2), "Filtrer cette colonne…")
    settle(app, window)
    assert window.view.filters == [Filter(1, "contains", "bob")]
    assert window.model.rowCount() == 1
    assert window.model.node(window.model.index(0, 0)).values[2] == "bob"


def test_import_dialog_never_overwrites_existing_file(app, tmp_path, monkeypatch):
    monkeypatch.setattr("timeline_next.dialogs.analyses_directory", lambda: tmp_path)
    source = tmp_path / "source.csv"
    source.write_text("ID\n001\n")
    existing = tmp_path / "source.timeline"
    existing.write_bytes(b"keep this")
    dialog = ImportDialog(source)
    assert Path(dialog.target.text()).name == "source-2.timeline"
    dialog.target.setText(str(existing))
    dialog.accept()
    assert dialog.result() != QDialog.Accepted
    assert dialog.message.text()
    assert existing.read_bytes() == b"keep this"
    dialog.target.setText(str(tmp_path / "source"))
    dialog.accept()
    assert dialog.result() != QDialog.Accepted
    assert existing.read_bytes() == b"keep this"
    dialog.target.setText("")
    dialog.accept()
    assert dialog.result() != QDialog.Accepted
    dialog.target.setText(str(tmp_path / "fresh"))
    dialog.accept()
    assert dialog.result() == QDialog.Accepted
    assert dialog.values()[0] == tmp_path / "fresh.timeline"
    assert dialog.values()[1:] == (None, "utf-8")


def test_drag_drop_import_unicode_path_and_reopen(app, tmp_path, monkeypatch):
    source = tmp_path / "enquête été.csv"
    source.write_text('User,ID\n"évidence",0001\nalice,0002\n', encoding="utf-8")
    original = hashlib.sha256(source.read_bytes()).hexdigest()
    target = tmp_path / "analyse été.timeline"
    def accept_import(dialog):
        dialog.target.setText(str(target))
        dialog.accept()
        return dialog.result()
    monkeypatch.setattr(ImportDialog, "exec", accept_import)
    window = Window()
    errors = []
    window.error = errors.append
    window.show()
    app.processEvents()
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(source))])
    drag = QDragEnterEvent(QPointF(20, 20), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(window, drag)
    assert drag.isAccepted()
    drop = QDropEvent(QPointF(20, 20), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(window, drop)
    assert drop.isAccepted()
    settle(app, window)
    assert window.model is not None
    assert window.content_stack.currentIndex() == 1
    assert window.case.page(View())[0][1:] == ("évidence", "0001")
    assert window.case.info["sha256"] == original
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original
    window.case.bookmark(1, "Keep")
    window.detach()
    assert window.content_stack.currentIndex() == 0
    window.open_path(target)
    settle(app, window)
    assert window.case.bookmarks() == {1: "Keep"}
    assert window.model.rowCount() == 2
    assert not errors
    assert window.close()


def test_bad_or_missing_case_does_not_close_current_analysis(app, window, tmp_path):
    original_case = window.case
    errors = []
    window.error = errors.append
    empty = tmp_path / "empty.timeline"
    Case(empty).close()
    window.open_path(empty)
    assert window.case is original_case
    window.open_path(tmp_path / "missing.timeline")
    assert window.case is original_case
    assert not (tmp_path / "missing.timeline").exists()
    assert window.model.rowCount() == 4
    assert len(errors) == 2


def test_drop_rejects_multiple_or_remote_files(app, window, tmp_path):
    mime = QMimeData()
    mime.setUrls([QUrl("https://example.com/evidence.csv")])
    assert Window.dropped_file(mime) is None
    first, second = tmp_path / "one.csv", tmp_path / "two.csv"
    first.write_text("ID\n1\n")
    second.write_text("ID\n2\n")
    mime.setUrls([QUrl.fromLocalFile(str(first)), QUrl.fromLocalFile(str(second))])
    assert Window.dropped_file(mime) is None
    mime.setUrls([QUrl.fromLocalFile(str(first))])
    assert Window.dropped_file(mime) == first


def test_interrupted_grid_can_retry_and_queued_count_is_cancelled(app, window, monkeypatch):
    import threading
    started, release = threading.Event(), threading.Event()
    native_page = window.case.page
    def waiting_page(*args, **kwargs):
        with window.case.operation():
            started.set()
            release.wait(3)
            window.case.check_cancelled()
        return native_page(*args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(window.case, "page", waiting_page)
        window.apply()
        assert started.wait(2)
        window.interrupt_queries()
        release.set()
        settle(app, window)
    assert window.count_label.text() == "Comptage interrompu"
    assert window.model.root.more and not window.model.root.loading
    window.more()
    settle(app, window)
    assert window.model.rowCount() == 4
    window.apply()
    settle(app, window)
    assert window.count_label.text() == "4 / 4 lignes"


def test_cancelled_exclusive_job_restores_desktop_controls(app, window):
    from timeline_next.errors import OperationCancelled
    completed = []
    def operation():
        raise OperationCancelled()
    window.run(operation, completed.append, exclusive=True)
    assert window.busy and not window.centralWidget().isEnabled()
    settle(app, window)
    assert not window.busy and window.centralWidget().isEnabled()
    assert all(action.isEnabled() for action in window.analysis_actions)
    assert not completed
    assert window.statusBar().currentMessage() == "Opération annulée."


def test_cancel_before_database_entry_is_not_lost(app, window):
    import threading
    entered, release = threading.Event(), threading.Event()
    completed = []
    def delayed_query():
        entered.set()
        release.wait(3)
        return window.case.count(View())
    window.run(delayed_query, completed.append)
    assert entered.wait(2)
    window.interrupt_queries()
    release.set()
    settle(app, window)
    assert not completed
    assert window.statusBar().currentMessage() == "Opération annulée."
    assert window.case.count(View()) == 4


def test_failed_import_reopens_previous_view_layout_and_notes(app, window, tmp_path, monkeypatch):
    old_path = window.case.path
    window.case.bookmark(1, "Keep this note")
    previous = View(search="alice", filters=[Filter(0, "eq", "MFT")], groups=[1],
                    sort_column=2, sort_type="number", descending=True, highlight="alice")
    window.set_view(previous)
    settle(app, window)
    window.tree.header().moveSection(1, 3)
    window.tree.setColumnHidden(3, True)
    window.tree.setColumnWidth(2, 280)
    bad_source = tmp_path / "malformed.csv"
    bad_source.write_text("a,b\n1,2\n3,4,5\n")
    target = tmp_path / "failed.timeline"
    def accept_import(dialog):
        dialog.target.setText(str(target))
        dialog.accept()
        return dialog.result()
    monkeypatch.setattr(ImportDialog, "exec", accept_import)
    errors = []
    window.error = errors.append
    window.import_file(bad_source)
    settle(app, window)
    assert len(errors) == 1
    assert window.case.path == old_path
    assert window.view == previous
    assert window.search.text() == "alice"
    assert window.case.count(window.view) == 2
    assert window.case.bookmarks() == {1: "Keep this note"}
    assert window.model.notes == {1: "Keep this note"}
    assert window.tree.header().visualIndex(1) == 3
    assert window.tree.isColumnHidden(3)
    assert window.tree.columnWidth(2) == 280
    assert window.content_stack.currentIndex() == 1
    assert window.can_open_file()


def test_cancelled_import_restores_previous_case_then_next_import_succeeds(app, window, tmp_path, monkeypatch):
    old_path = window.case.path
    window.tree.setColumnHidden(1, True)
    new_source = tmp_path / "new.csv"
    new_source.write_text("NewID\n0009\n0010\n")
    target = tmp_path / "cancelled.timeline"
    def accept_import(dialog):
        dialog.target.setText(str(target))
        dialog.accept()
        return dialog.result()
    monkeypatch.setattr(ImportDialog, "exec", accept_import)
    native_import = Case.import_csv
    def cancelling_import(case, source, delimiter=None, encoding="utf-8", progress=lambda _: None):
        def forward(message):
            progress(message)
            if message == "Validation de l’analyse…":
                case.interrupt()
        return native_import(case, source, delimiter, encoding, forward)
    with monkeypatch.context() as patch:
        patch.setattr(Case, "import_csv", cancelling_import)
        window.import_file(new_source)
        settle(app, window)
    assert window.case.path == old_path
    assert window.model.rowCount() == 4
    assert window.tree.isColumnHidden(1)
    assert not window.busy and window.can_open_file()
    target = tmp_path / "success.timeline"
    window.import_file(new_source)
    settle(app, window)
    assert window.case.path == target
    assert window.case.headers == ["NewID"]
    assert window.view == View()
    assert window.model.rowCount() == 2
    assert not window.tree.isColumnHidden(1)
    assert window.case.page(View())[0][1] == "0009"


def test_first_import_cancel_returns_to_welcome(app, tmp_path, monkeypatch):
    from timeline_next.errors import OperationCancelled
    source = tmp_path / "source.csv"
    source.write_text("ID\n001\n")
    target = tmp_path / "cancelled.timeline"
    def accept_import(dialog):
        dialog.target.setText(str(target))
        dialog.accept()
        return dialog.result()
    def cancel_import(*args, **kwargs):
        raise OperationCancelled()
    monkeypatch.setattr(ImportDialog, "exec", accept_import)
    monkeypatch.setattr(Case, "import_csv", cancel_import)
    w = Window()
    errors = []
    w.error = errors.append
    w.import_file(source)
    settle(app, w)
    assert w.case is None and w.model is None
    assert w.content_stack.currentIndex() == 0
    assert not w.busy and w.centralWidget().isEnabled()
    assert w.can_open_file()
    assert not errors
    assert w.close()


def test_restore_does_not_recreate_missing_or_replaced_analysis(app, window, tmp_path):
    snapshot = window.snapshot_analysis()
    window.detach()
    Path(snapshot.path).unlink()
    error = window.restore_after_import(snapshot)
    assert error and "introuvable" in error
    assert not Path(snapshot.path).exists()
    replacement_source = tmp_path / "replacement.csv"
    replacement_source.write_text("Changed\n42\n")
    replacement = Case(snapshot.path)
    replacement.import_csv(replacement_source)
    replacement.close()
    error = window.restore_after_import(snapshot)
    assert error and "remplacée" in error
    assert window.case is None and window.model is None
    assert window.content_stack.currentIndex() == 0


def test_restore_rejects_different_decoding_of_the_same_source(app, tmp_path):
    source = tmp_path / "unicode.csv"
    source.write_text("User\névidence\n", encoding="utf-8")
    case_path = tmp_path / "unicode.timeline"
    original = Case(case_path)
    original.import_csv(source)
    window = Window()
    window.attach(original)
    settle(app, window)
    snapshot = window.snapshot_analysis()
    window.detach()
    case_path.unlink()
    replacement = Case(case_path)
    replacement.import_csv(source, encoding="latin-1")
    assert replacement.info["sha256"] == snapshot.source_info["sha256"]
    assert replacement.info["encoding"] != snapshot.source_info["encoding"]
    replacement.close()
    error = window.restore_after_import(snapshot)
    assert error and "remplacée" in error
    assert window.case is None and window.model is None
    assert window.close()
