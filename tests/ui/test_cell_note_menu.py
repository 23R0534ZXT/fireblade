"""The cell note is offered where the user writes it: the context menu and the dialogue."""
import pytest
from PySide6.QtGui import QStandardItemModel

from fireblade.core.i18n import set_language
from fireblade.ui.language import install, translate_tree
from fireblade.ui.menus import cell_menu


class _Node:
    group = False
    footer = False
    values = [7, "a value", "another"]   # the row id is an int, as the engine writes it


class _Model:
    notes = {}
    cell_notes = {}

    def node(self, index):
        return _Node()

    def update_cell_note(self, row_id, column, note):
        self.cell_notes = dict(self.cell_notes)
        if note is None:
            self.cell_notes.pop((row_id, column), None)
        else:
            self.cell_notes[(row_id, column)] = note


class _Case:
    headers = ["Time", "User", "Artifact"]

    def bookmark(self, row_id, note, column=None):
        self.calls = getattr(self, "calls", []) + [(row_id, note, column)]

    def validate_view(self, view):
        return None

    def bookmark_many(self, ids, note="", mode="mark"):
        self.many = getattr(self, "many", []) + [(ids, note, mode)]

    def close(self):
        return None


@pytest.fixture
def window(qt_application):
    from fireblade.ui.app import Window
    install(qt_application)
    widget = Window(require_case=False)
    widget.model = _Model()
    widget.case = _Case()
    widget.apply = lambda *args, **kwargs: None    # the stub model has no rows to reload
    yield widget
    widget.model = None
    widget.case = None
    widget.close()


def _labels(menu):
    translate_tree(menu)          # what the application does when the menu pops up
    return [action.text() for action in menu.actions() if not action.isSeparator()]


def test_the_menu_offers_to_add_a_note_on_an_empty_cell(window, monkeypatch):
    monkeypatch.setattr(window, "selection_note", lambda: (0, ""))
    try:
        set_language("en")
        index = QStandardItemModel(1, 3).index(0, 1)
        labels = _labels(cell_menu(window, index))
        assert "Add a note to the cell…" in labels
        assert "Edit the cell note…" not in labels
    finally:
        set_language("fr")


def test_the_menu_offers_to_edit_the_note_of_a_noted_cell(window, monkeypatch):
    monkeypatch.setattr(window, "selection_note", lambda: (0, ""))
    window.model.cell_notes = {(7, 1): "already here"}
    try:
        set_language("en")
        index = QStandardItemModel(1, 3).index(0, 2)   # display column 2 = data column 1
        labels = _labels(cell_menu(window, index))
        assert "Edit the cell note…" in labels
        assert "Add a note to the cell…" not in labels
    finally:
        set_language("fr")


def test_the_dialogue_opens_on_the_existing_note(window, monkeypatch):
    """The reported bug: reopening the cell showed nothing instead of the note."""
    from PySide6.QtWidgets import QInputDialog

    window.model.cell_notes = {(7, 1): "already here"}
    shown = {}

    def fake_dialog(parent, title, prompt, text=""):
        shown["title"], shown["prompt"], shown["text"] = title, prompt, text
        return "already here and more", True

    monkeypatch.setattr(QInputDialog, "getMultiLineText", staticmethod(fake_dialog))
    monkeypatch.setattr(window, "run", lambda job, done=None, **kwargs: done(job()))
    window.edit_bookmark(7, 1)

    assert shown["text"] == "already here", "the existing note must be pre-filled"
    assert "User" in shown["prompt"], "the dialogue names the column"
    assert window.case.calls == [(7, "already here and more", 1)]


def test_an_empty_note_removes_the_cell_note(window, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    window.model.cell_notes = {(7, 1): "to delete"}
    monkeypatch.setattr(QInputDialog, "getMultiLineText",
                        staticmethod(lambda *args, **kwargs: ("", True)))
    monkeypatch.setattr(window, "run", lambda job, done=None, **kwargs: done(job()))
    window.edit_bookmark(7, 1)
    assert window.case.calls == [(7, None, 1)]

def _select(window, rows, model_rows=3):
    """Give the window a selection of data rows, as the grid would."""
    from PySide6.QtCore import QItemSelectionModel
    model = QStandardItemModel(model_rows, 3)
    window.tree.selectionModel().select(
        model.index(0, 0), QItemSelectionModel.Select | QItemSelectionModel.Rows)
    window.tree.selectionModel()._fake = model          # keep the model alive
    return model


def test_the_selection_menu_offers_to_edit_when_a_note_exists(window, monkeypatch):
    window.model.notes = {7: "a note on the row"}
    selected = [(7, 0)]
    monkeypatch.setattr(window, "selection_ids", lambda: [row for row, _ in selected])
    monkeypatch.setattr(window, "selection_note", lambda: (1, "a note on the row"))
    try:
        set_language("en")
        index = QStandardItemModel(1, 3).index(0, 1)
        labels = _labels(cell_menu(window, index))
        assert "Edit the selection note…" in labels
        assert "Add a note to the selection…" not in labels
    finally:
        set_language("fr")


def test_the_selection_menu_adds_when_no_note_exists(window, monkeypatch):
    monkeypatch.setattr(window, "selection_note", lambda: (0, ""))
    try:
        set_language("en")
        index = QStandardItemModel(1, 3).index(0, 1)
        labels = _labels(cell_menu(window, index))
        assert "Add a note to the selection…" in labels
        assert "Edit the selection note…" not in labels
    finally:
        set_language("fr")


def test_editing_a_selection_prefills_the_common_note(window, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    shown = {}

    def fake_dialog(parent, title, prompt, text=""):
        shown["title"], shown["prompt"], shown["text"] = title, prompt, text
        return "corrected", True

    monkeypatch.setattr(QInputDialog, "getMultiLineText", staticmethod(fake_dialog))
    monkeypatch.setattr(window, "selection_ids", lambda: [7, 8])
    monkeypatch.setattr(window, "selection_note", lambda: (2, "the same note"))
    monkeypatch.setattr(window, "run", lambda job, done=None, **kwargs: done(job()))
    window.annotate_selection("replace")

    assert shown["text"] == "the same note"
    assert window.case.many == [([7, 8], "corrected", "replace")]
