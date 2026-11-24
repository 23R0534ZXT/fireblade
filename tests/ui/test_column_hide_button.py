"""The small cross on the right of a column header hides that column.

Hiding a column used to need the column manager or a drag above the header; the analyst
asked for the same gesture the tab bar already has.
"""

from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QTableView

from fireblade.ui.grouping import GroupHeader


def build(qt_application):
    table = QTableView()
    header = GroupHeader(table)
    model = QStandardItemModel(1, 4)
    model.setHorizontalHeaderLabels(["Row /…", "Artefact", "Source file", "EventId"])
    model.setItem(0, 0, QStandardItem("1"))
    table.setModel(model)
    table.setHorizontalHeader(header)
    header.sync_filters([], None, False)
    return table, header


def test_every_column_but_the_row_number_has_a_hide_button(qt_application):
    table, header = build(qt_application)
    try:
        assert set(header.controls) == {1, 2, 3}
        for section in header.controls:
            close = header.controls[section][3]
            assert close.text() == "×"
            assert close.toolTip()
    finally:
        table.deleteLater()


def test_pressing_the_cross_asks_to_hide_that_column(qt_application):
    table, header = build(qt_application)
    hidden = []
    header.hideRequested.connect(hidden.append)
    try:
        header.controls[2][3].click()
        assert hidden == [1], hidden  # zero-based column, first section is the row number
    finally:
        table.deleteLater()


def test_a_narrow_column_does_not_show_a_cross_it_cannot_fit(qt_application):
    table, header = build(qt_application)
    try:
        header.resizeSection(1, 40)
        header.position_controls()
        assert not header.controls[1][3].isVisibleTo(header.viewport())
        header.resizeSection(1, 200)
        header.position_controls()
        assert header.controls[1][3].isVisibleTo(header.viewport())
    finally:
        table.deleteLater()
