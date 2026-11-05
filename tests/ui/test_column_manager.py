"""Column manager: visibility, order, width and pinning without a live grid."""
from fireblade.ui.column_manager import ColumnManager

HEADERS = ["Time", "Artifact", "User", "EventID", "Message"]


def build(**state):
    return ColumnManager(HEADERS, state)


def test_columns_are_split_between_the_two_panes():
    dialog = build(order=[0, 1, 2, 3, 4], hidden=[3])
    try:
        assert dialog.showing == [0, 1, 2, 4]
        assert dialog.available == [3]
        assert dialog.right.count() == 4 and dialog.left.count() == 1
    finally:
        dialog.deleteLater()


def test_showing_and_hiding_moves_the_column_and_keeps_the_order():
    dialog = build(order=[0, 1, 2], hidden=[3, 4])
    try:
        dialog.show_column(3)
        assert dialog.showing == [0, 1, 2, 3]
        assert dialog.state()["hidden"] == [4]
        dialog.hide_column(1)
        assert dialog.showing == [0, 2, 3]
        assert 1 in dialog.state()["hidden"]
    finally:
        dialog.deleteLater()


def test_a_column_can_be_inserted_at_a_given_position():
    dialog = build(order=[0, 1], hidden=[2])
    try:
        dialog.show_column(2, position=1)
        assert dialog.showing == [0, 2, 1]
    finally:
        dialog.deleteLater()


def test_width_and_pinning_are_reported_for_visible_columns_only():
    dialog = build(order=[0, 1, 2], hidden=[3, 4])
    try:
        dialog.set_width(1, 180)
        dialog.set_pin(1, "left")
        dialog.set_pin(2, "right")
        dialog.set_width(3, 999)  # hidden: width is not applied
        result = dialog.state()
        assert result["widths"] == {1: 180}
        assert result["left"] == [1] and result["right"] == [2]
    finally:
        dialog.deleteLater()


def test_pane_order_is_the_display_order():
    dialog = build(order=[0, 1, 2])
    try:
        item = dialog.right.takeItem(0)
        dialog.right.insertItem(2, item)
        assert dialog.state()["order"][:3] == [1, 2, 0]
    finally:
        dialog.deleteLater()


def test_an_unknown_pin_is_rejected():
    dialog = build(order=[0])
    try:
        try:
            dialog.set_pin(0, "middle")
        except ValueError:
            pass
        else:
            raise AssertionError("un épinglage inconnu doit être refusé")
        assert dialog.state()["left"] == []
    finally:
        dialog.deleteLater()


def test_apply_controls_writes_the_selected_column():
    dialog = build(order=[0, 1])
    try:
        dialog._select(dialog.right, 1)
        dialog.sync_controls()
        dialog.width.setValue(240)
        dialog.pin.setCurrentIndex(dialog.pin.findData("right"))
        assert dialog.state()["widths"] == {1: 240}
        assert dialog.state()["right"] == [1]
    finally:
        dialog.deleteLater()
