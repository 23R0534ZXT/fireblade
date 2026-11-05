import hashlib
import os
from pathlib import Path
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QLineEdit

from fireblade.ui.app import Window
from fireblade.ui.dialogs import ImportDialog
from fireblade.core.engine import Case
from fireblade.ui.menus import cell_menu, header_menu
from fireblade.core.models import Filter, View
from fireblade.ui.theme import apply_theme


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
    w = Window(require_case=False)
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
    monkeypatch.setattr("fireblade.ui.dialogs.analyses_directory", lambda: tmp_path)
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
    assert dialog.values()[1:] == (None, "auto")
    dialog.encoding.setCurrentIndex(dialog.encoding.findData("cp1252"))
    assert dialog.values()[2] == "cp1252"


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
    window = Window(require_case=False)
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
    from fireblade.core.errors import OperationCancelled
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
    assert window.model.notes == {}  # Collapsed groups hold no row annotations.
    window.model.fetchMore(window.model.index(0, 0))
    settle(app, window)
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
    from fireblade.core.errors import OperationCancelled
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
    w = Window(require_case=False)
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
    window = Window(require_case=False)
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


def test_tle_shortcuts_act_on_raw_cell_and_clear_filters(app,window):
    from PySide6.QtTest import QTest
    window.activateWindow();window.tree.setFocus()
    index=window.model.index(0,3)
    window.tree.setCurrentIndex(index)
    QTest.keyClick(window.tree,Qt.Key_F,Qt.ControlModifier|Qt.ShiftModifier)
    settle(app,window)
    assert window.view.filters==[Filter(2,'eq','001')]
    assert window.case.count(window.view)==1
    QTest.keyClick(window.tree,Qt.Key_E,Qt.ControlModifier)
    settle(app,window)
    assert window.view.filters==[] and window.case.count(window.view)==4
    window.group_column(0);settle(app,window)
    QTest.keyClick(window.tree,Qt.Key_M,Qt.ControlModifier)
    settle(app,window)
    assert window.view.expand_all
    assert not window.case.bookmarks([1,2,3,4])
    QTest.keyClick(window.tree,Qt.Key_K,Qt.ControlModifier)
    settle(app,window)
    assert not window.view.expand_all


def test_current_cell_filter_handles_null_and_ignores_group_and_line(app,window):
    window.tree.setCurrentIndex(window.model.index(3,2));window.filter_current_cell();settle(app,window)
    assert window.view.filters==[Filter(1,'empty')]
    window.clear_filters();settle(app,window)
    window.tree.setCurrentIndex(window.model.index(0,0));window.filter_current_cell()
    assert not window.view.filters
    window.group_column(0);settle(app,window)
    window.tree.setCurrentIndex(window.model.index(0,1));window.filter_current_cell()
    assert not window.view.filters


def test_all_date_group_intervals_are_accessible_in_header_menu(app,window):
    menu=header_menu(window,2)
    dates=next(action.menu() for action in menu.actions() if action.text()=='Regrouper les dates par')
    try:
        assert [action.text() for action in dates.actions()]==['Valeur entière','Année','Trimestre','Mois','Semaine','Jour','Heure','Minute','Seconde']
        next(action for action in dates.actions() if action.text()=='Semaine').trigger();settle(app,window)
        assert window.view.group_intervals['1']=='week'
    finally:menu.deleteLater()


def test_inline_filters_sort_pins_and_clear(app, window):
    from PySide6.QtTest import QTest
    header = window.tree.header()
    edit, up, down = header.controls[2]
    QTest.keyClicks(edit, "ali")
    QTest.qWait(500)
    settle(app, window)
    assert window.case.count(window.view) == 2
    assert edit.text() == "ali"
    # Filtering a second column combines with ET and preserves the first filter.
    QTest.keyClicks(header.controls[3][0], "001")
    QTest.keyClick(header.controls[3][0], Qt.Key_Return)
    settle(app, window)
    assert window.case.count(window.view) == 1
    window.clear_filters()
    settle(app, window)
    assert all(not widgets[0].text() for widgets in header.controls.values())
    QTest.mouseClick(down, Qt.LeftButton)
    settle(app, window)
    assert window.view.sort_column == 1 and window.view.descending
    assert down.isChecked() and not up.isChecked()
    window.pin_column(1)
    settle(app, window)
    frozen_header = window.tree.frozen.header()
    assert frozen_header.controls[2][0].isVisible()
    QTest.keyClicks(frozen_header.controls[2][0], "bob")
    QTest.keyClick(frozen_header.controls[2][0], Qt.Key_Return)
    settle(app, window)
    assert window.case.count(window.view) == 1
    assert header.controls[2][0].text() == "bob"
    window.clear_filters()
    settle(app, window)
    QTest.mouseClick(frozen_header.controls[2][1], Qt.LeftButton)
    settle(app, window)
    assert not window.view.descending


def test_group_chips_remove_one_level(app, window):
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QToolButton
    window.group_column(0)
    window.group_column(1, append=True)
    settle(app, window)
    chips = window.groups_label.findChildren(QToolButton)
    chips = [chip for chip in chips if chip.isVisible() and chip is not window.groups_label.clear_button]
    assert [chip.text() for chip in chips] == ["1  Artifact  ×", "2  User  ×"]
    QTest.mouseClick(chips[0], Qt.LeftButton)
    settle(app, window)
    assert window.view.groups == [1]


def test_group_bar_clears_every_level(app, window):
    from PySide6.QtTest import QTest
    window.group_column(0)
    window.group_column(1, append=True)
    window.group_column(2, append=True)
    settle(app, window)
    assert window.view.groups == [0, 1, 2]
    assert not window.groups_label.clear_button.isHidden()
    QTest.mouseClick(window.groups_label.clear_button, Qt.LeftButton)
    settle(app, window)
    assert window.view.groups == []
    assert window.groups_label.clear_button.isHidden()


def test_group_drop_inserts_where_the_level_is_released(app, window):
    window.group_column(0)
    window.group_column(1, append=True)
    settle(app, window)
    # Moving an existing level to the end keeps it once, at that position.
    window.group_column(0, append=True, position=2)
    settle(app, window)
    assert window.view.groups == [1, 0]
    # A new level dropped between two others is inserted, not appended.
    window.group_column(2, append=True, position=1)
    settle(app, window)
    assert window.view.groups == [1, 2, 0]


def test_command_palette_lists_and_filters_menu_commands(app, window):
    from fireblade.ui.command_palette import CommandPalette, flatten_actions
    entries = flatten_actions(window.menuBar())
    labels = [label for label, _action in entries]
    assert len(labels) > 20
    assert any('Colonnes' in label for label in labels)
    palette = CommandPalette(window)
    try:
        total = palette.listing.count()
        assert total == len(entries)
        palette.filter('colonnes')
        assert 0 < palette.listing.count() < total
        palette.filter('')
        assert palette.listing.count() == total
    finally:
        palette.deleteLater()


def test_boolean_cards_invert_preserves_nested_siblings(app):
    from fireblade.ui.advanced_dialogs import ExpressionEditor
    from fireblade.core.models import FilterGroup
    expression = FilterGroup("and", [Filter(0, "contains", "alice"), Filter(1, "eq", "MFT")])
    editor = ExpressionEditor(["User", "Artifact"], expression)
    editor.root.children[0].inverse.setChecked(True)
    assert editor.value() == FilterGroup("and", [FilterGroup("not", [expression.children[0]]), expression.children[1]])
    editor.root.children[0].inverse.setChecked(False)
    assert editor.value() == expression
    editor.root.inverse.setChecked(True)
    assert editor.value() == FilterGroup("not", [expression])
    editor.root.inverse.setChecked(False)
    assert editor.value() == expression
    single = ExpressionEditor(["User"], FilterGroup("not", [Filter(0, "eq", "alice")]))
    single.root.children[0].inverse.setChecked(False)
    assert single.value() == Filter(0, "eq", "alice")
    single.add_node(single.root, Filter(0, "contains", "bob"))
    assert len(single.value().children) == 2
    single.close()
    editor.close()


def test_header_controls_follow_layout_and_cancel_pending_on_view_change(app, window):
    from PySide6.QtTest import QTest
    header = window.tree.header()
    for column in range(header.count()):
        window.tree.setColumnWidth(column, 400)
    header.moveSection(header.visualIndex(2), 1)
    window.tree.horizontalScrollBar().setValue(150)
    app.processEvents()
    edit = header.controls[2][0]
    assert edit.x() == header.sectionViewportPosition(2) + 3
    assert edit.width() == header.sectionSize(2) - 6
    window.tree.setColumnHidden(2, True)
    app.processEvents()
    assert edit.isHidden()
    window.tree.setColumnHidden(2, False)
    app.processEvents()
    assert not edit.isHidden()
    # A pending debounce must not filter another tab/restored view later.
    QTest.keyClicks(edit, "alice")
    window.set_view(View(filters=[Filter(1, "contains", "bob")]))
    QTest.qWait(500)
    settle(app, window)
    assert window.case.count(window.view) == 1
    assert edit.text() == "bob"
    assert View.from_json(window.view.to_json()).filters == [Filter(1, "contains", "bob")]
