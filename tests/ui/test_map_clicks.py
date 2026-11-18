"""A ray is four pixels wide: clicking it must work, and so must clicking near it."""
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from fireblade.ui.maps import CircularMap


class Group:
    """The little the dial reads: a key, a severity, a count and two stamps."""

    def __init__(self, key, level, start, count=1):
        self.key = key
        self.level = level
        self.title = 'rule ' + key
        self.host = 'PC01'
        self.channel = 'System'
        self.count = count
        self.start = start
        self.end = start
        self.event_ids = ('7045',)


def _dial(qt_application):
    dial = CircularMap()
    dial.resize(620, 460)
    dial.set_data([Group('a', 'high', datetime(2026, 11, 14, 14, 20), 6),
                   Group('b', 'medium', datetime(2026, 11, 14, 9, 15), 2)], [])
    dial.grab()          # paints once, which is what registers the clickable marks
    return dial


def test_the_dial_registers_a_clickable_area_for_every_ray(qt_application):
    dial = _dial(qt_application)
    assert dial._marks
    assert len(dial._marks) == 2


def test_a_click_on_the_ray_selects_its_finding(qt_application):
    dial = _dial(qt_application)
    shape, key = dial._marks[0]
    chosen = []
    dial.group_selected.connect(chosen.append)

    QTest.mouseClick(dial, Qt.LeftButton, pos=shape.boundingRect().center().toPoint())

    expected = next(index for index, group in enumerate(dial.groups) if group.key == key)
    assert chosen == [expected]
    assert dial.selected_key == key


def test_the_whole_ray_answers_the_click_not_only_its_tip(qt_application):
    """The tip was the only target before: the line itself ignored the click."""
    dial = _dial(qt_application)
    shape, key = dial._marks[0]
    box = shape.boundingRect()

    assert dial.mark_at(box.center()) == key
    # A sixteen-pixel square around the tip would be shorter than the ray it stands for.
    assert max(box.width(), box.height()) > 30


def test_a_click_on_empty_canvas_selects_nothing(qt_application):
    dial = _dial(qt_application)
    chosen = []
    dial.group_selected.connect(chosen.append)

    QTest.mouseClick(dial, Qt.LeftButton, pos=dial.rect().topLeft() + dial.rect().topLeft() / 2)

    assert chosen == []
