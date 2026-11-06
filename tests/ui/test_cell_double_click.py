"""A double-click reads a cell; it no longer opens the note editor."""
import pytest
from PySide6.QtGui import QStandardItemModel


class _Node:
    group = False
    footer = False
    values = ["row-id", "a value", "another"]


class _Model:
    def node(self, index):
        return _Node()


@pytest.fixture
def window(qt_application):
    from fireblade.ui.app import Window
    widget = Window(require_case=False)
    yield widget
    widget.model = None
    widget.close()


def test_a_double_click_on_a_data_cell_opens_the_cell_viewer(window, monkeypatch):
    opened = []
    edited = []
    monkeypatch.setattr(window, "cell_details", lambda index=None: opened.append(index))
    monkeypatch.setattr(window, "edit_bookmark", lambda row: edited.append(row))
    window.model = _Model()
    model = QStandardItemModel(1, 3)

    window.cell_double_clicked(model.index(0, 1))

    assert len(opened) == 1
    assert not edited, "a double-click must not open the note editor"
    assert opened[0].column() == 1


def test_a_double_click_on_the_bookmark_column_does_nothing(window, monkeypatch):
    opened = []
    monkeypatch.setattr(window, "cell_details", lambda index=None: opened.append(index))
    window.model = _Model()
    model = QStandardItemModel(1, 3)

    window.cell_double_clicked(model.index(0, 0))

    assert not opened


def test_the_grid_signal_reaches_the_cell_viewer(window, monkeypatch):
    """The gesture the user asked for is the one installed on the grid."""
    opened = []
    monkeypatch.setattr(window, "cell_details", lambda index=None: opened.append(index))
    window.model = _Model()
    model = QStandardItemModel(1, 3)

    window.tree.doubleClicked.emit(model.index(0, 2))

    assert len(opened) == 1 and opened[0].column() == 2
