"""Three painted maps of a finding set: the dial, the heat map, and the chain.

They are deliberately plain ``QWidget`` subclasses drawing with ``QPainter``: no charting
dependency, no QtQuick, and every mark is a function of the data so the same findings
always give the same picture — which is what makes a capture in a test meaningful.

Each map emits ``group_selected(key)`` when the analyst clicks a mark, and exposes
``set_data(groups, incidents)`` and ``select(key)``. Whatever they cannot draw — a
group with no timestamp — they count and report through ``unplaced()`` instead of
hiding it.
"""
from __future__ import annotations

import math
from datetime import timedelta

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QSizePolicy, QWidget

LEVEL_COLOURS = {
    'critical': QColor('#d93a3a'),
    'high': QColor('#e07b39'),
    'medium': QColor('#c9a227'),
    'low': QColor('#5c9c4a'),
    'informational': QColor('#8c98a8'),
}
DARK = QColor('#141d2b')
INK = QColor('#e7edf7')
INK_SOFT = QColor('#93a2b8')
INK_FAINT = QColor('#5d6f8a')


def _hit_radius(group):
    return 4.0 + min(9.0, math.log1p(group.count) * 1.8)


class FindingMap(QWidget):
    """Common behaviour: data, selection, hit-testing and an honest 'not drawn' count."""

    group_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.groups = []
        self.incidents = []
        self.selected_key = ''
        self._marks = []          # (rect/point, key)
        self.unplaced = 0
        # Small on purpose: the tab must not raise the window's minimum height,
        # or the 1024x600 check fails on a machine with a small screen.
        self.setMinimumHeight(96)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)

    def set_data(self, groups, incidents):
        self.groups = list(groups)
        self.incidents = list(incidents)
        self.unplaced = 0
        self.update()

    def select(self, key):
        self.selected_key = key
        self.update()

    def mousePressEvent(self, event):
        position = event.position()
        for rect, key in reversed(self._marks):
            if rect.contains(position):
                self.selected_key = key
                index = next((i for i, g in enumerate(self.groups) if g.key == key), -1)
                if index >= 0:
                    self.group_selected.emit(index)
                self.update()
                return
        super().mousePressEvent(event)

    # a shared frame: dark backdrop, a title, a legend
    def paint_frame(self, painter, title, subtitle, legend=True):
        painter.fillRect(self.rect(), DARK)
        painter.setPen(INK)
        font = QFont(self.font())
        font.setPointSizeF(font.pointSizeF() + 1.5)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(12, 6, self.width() - 24, 20), int(Qt.AlignLeft | Qt.AlignVCenter), title)
        painter.setPen(INK_SOFT)
        font.setBold(False)
        font.setPointSizeF(max(7.5, font.pointSizeF() - 2.5))
        painter.setFont(font)
        painter.drawText(QRectF(12, 26, self.width() - 24, 16), int(Qt.AlignLeft | Qt.AlignVCenter), subtitle)
        if legend:
            x = self.width() - 12
            for level in ('informational', 'low', 'medium', 'high', 'critical'):
                x -= 62
                painter.setBrush(LEVEL_COLOURS[level])
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QPointF(x + 5, 16), 3.5, 3.5)
                painter.setPen(INK_SOFT)
                painter.drawText(QRectF(x + 12, 8, 52, 16), int(Qt.AlignLeft | Qt.AlignVCenter), level[:5])
        if self.unplaced:
            painter.setPen(QColor('#c9a227'))
            painter.drawText(QRectF(12, self.height() - 18, self.width() - 24, 14),
                             int(Qt.AlignRight | Qt.AlignVCenter),
                             '%d finding(s) without a usable timestamp are not drawn' % self.unplaced)


class CircularMap(FindingMap):
    """The day as a dial: angle = time, distance from the centre = severity."""

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self._marks = []
        painter.fillRect(self.rect(), DARK)
        self.paint_frame(painter, 'The day at a glance',
                         'angle = time of day · distance from the centre = severity')
        if not self.groups:
            painter.setPen(INK_SOFT)
            painter.drawText(self.rect(), int(Qt.AlignCenter), 'No findings to place.')
            return
        area = self.rect().adjusted(12, 40, -12, -22)
        centre = QPointF(area.center())
        radius = min(area.width(), area.height()) / 2 - 26
        if radius <= 10:
            return
        start = min((group.start for group in self.groups if group.start), default=None)
        end = max((group.end for group in self.groups if group.end), default=None)
        self.unplaced = sum(1 for group in self.groups if group.start is None)
        if start is None:
            painter.setPen(INK_SOFT)
            painter.drawText(self.rect(), int(Qt.AlignCenter), 'None of the findings carries a timestamp.')
            return
        # A single instant still needs a dial: give it one hour to sit on.
        if end is None or end <= start:
            end = start + timedelta(hours=1)
        span = (end - start).total_seconds() or 1.0
        rings = {'informational': .40, 'low': .55, 'medium': .70, 'high': .85, 'critical': 1.0}
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor('#24344c'), 1))
        for fraction in rings.values():
            painter.drawEllipse(centre, radius * fraction, radius * fraction)
        # hour marks when the window is long enough to have any
        if span >= 7200:
            for tick in range(0, 25):
                angle = math.pi * 2 * tick / 24 - math.pi / 2
                inner = radius * (1.0 if tick % 3 else 1.03)
                painter.drawLine(QPointF(centre.x() + math.cos(angle) * radius * .98, centre.y() + math.sin(angle) * radius * .98),
                                 QPointF(centre.x() + math.cos(angle) * inner, centre.y() + math.sin(angle) * inner))
        gradient = QRadialGradient(centre, radius)
        gradient.setColorAt(0, QColor('#1d2a3d'))
        gradient.setColorAt(1, DARK)
        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(centre, radius * .38, radius * .38)
        painter.setBrush(Qt.NoBrush)
        for group in self.groups:
            if group.start is None:
                continue
            offset = (group.start - start).total_seconds() / span
            angle = math.pi * 2 * offset - math.pi / 2
            distance = radius * rings.get(group.level, .4)
            point = QPointF(centre.x() + math.cos(angle) * distance, centre.y() + math.sin(angle) * distance)
            colour = LEVEL_COLOURS.get(group.level, LEVEL_COLOURS['informational'])
            size = _hit_radius(group)
            if group.key == self.selected_key:
                painter.setPen(QPen(QColor('#ffffff'), 1.4))
                painter.setBrush(QColor(colour.red(), colour.green(), colour.blue(), 70))
                painter.drawEllipse(point, size + 6, size + 6)
                painter.setBrush(Qt.NoBrush)
            painter.setPen(Qt.NoPen)
            painter.setBrush(colour)
            painter.drawEllipse(point, size, size)
            self._marks.append((QRectF(point.x() - size - 2, point.y() - size - 2, size * 2 + 4, size * 2 + 4),
                                group.key))
        painter.setPen(INK_SOFT)
        painter.drawText(QRectF(centre.x() - 120, centre.y() - 22, 240, 16), int(Qt.AlignCenter),
                         start.strftime('%Y-%m-%d %H:%M'))
        painter.drawText(QRectF(centre.x() - 120, centre.y() + 2, 240, 16), int(Qt.AlignCenter),
                         'to ' + end.strftime('%H:%M'))
        painter.drawText(QRectF(centre.x() - 120, centre.y() + 20, 240, 16), int(Qt.AlignCenter),
                         '%d findings' % len(self.groups))


class HeatMap(FindingMap):
    """One row per rule, one column per time slice: brightness is how many hits fell there."""

    BUCKETS = 96

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        self._marks = []
        painter.fillRect(self.rect(), DARK)
        self.paint_frame(painter, 'Findings over time',
                         'one row per rule · brightness = hits in that slice · click a cell')
        if not self.groups:
            painter.setPen(INK_SOFT)
            painter.drawText(self.rect(), int(Qt.AlignCenter), 'No findings to place.')
            return
        start = min((group.start for group in self.groups if group.start), default=None)
        end = max((group.end for group in self.groups if group.end), default=None)
        self.unplaced = sum(1 for group in self.groups if group.start is None)
        if start is None:
            painter.setPen(INK_SOFT)
            painter.drawText(self.rect(), int(Qt.AlignCenter), 'None of the findings carries a timestamp.')
            return
        if end is None or end <= start:
            end = start + timedelta(hours=1)
        span = max(1.0, (end - start).total_seconds())
        label_width = min(260, max(120, self.width() // 3))
        area = QRectF(label_width, 44, self.width() - label_width - 12, self.height() - 70)
        rows = max(1, min(len(self.groups), int(area.height() // 16)))
        step = max(1, len(self.groups) // rows)
        shown = self.groups[::step][:rows]
        cell_h = area.height() / max(1, len(shown))
        cell_w = area.width() / self.BUCKETS
        font = QFont(self.font())
        font.setPointSizeF(max(7.0, font.pointSizeF() - 2.0))
        painter.setFont(font)
        for row, group in enumerate(shown):
            if group.start is None:
                continue
            offset = (group.start - start).total_seconds() / span
            column = min(self.BUCKETS - 1, int(offset * self.BUCKETS))
            colour = LEVEL_COLOURS.get(group.level, LEVEL_COLOURS['informational'])
            intensity = 0.35 + min(0.65, math.log1p(group.count) / 6)
            shade = QColor(colour)
            shade.setAlphaF(intensity)
            rect = QRectF(area.left() + column * cell_w, area.top() + row * cell_h, max(2.0, cell_w), cell_h - 1)
            if group.key == self.selected_key:
                painter.fillRect(rect.adjusted(-1, -1, 1, 1), QColor('#ffffff'))
            painter.fillRect(rect, shade)
            painter.setPen(INK_SOFT)
            painter.drawText(QRectF(6, rect.top(), label_width - 10, cell_h), int(Qt.AlignLeft | Qt.AlignVCenter),
                             group.title[:48])
            self._marks.append((QRectF(rect.left() - 1, rect.top() - 1, rect.width() + 2, cell_h), group.key))
        painter.setPen(INK_FAINT)
        for tick in range(0, 5):
            x = area.left() + area.width() * tick / 4
            moment = start + timedelta(seconds=span * tick / 4)
            label = moment.strftime('%d %H:%M')
            painter.drawText(QRectF(x - 40, area.bottom() + 2, 80, 16), int(Qt.AlignCenter), label)


class ChainMap(FindingMap):
    """What sits in the same incident window, host by host — the order of events, not a hop graph.

    A real 'what the assistant linked' picture arrives with the engine, which is the only
    thing that knows which link it asserts. Drawing hops before that would invent them.
    """

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self._marks = []
        painter.fillRect(self.rect(), DARK)
        self.paint_frame(painter, 'One incident window, in order',
                         'hosts as lanes · marks in time order · a line means the same window, not a proven link')
        if not self.groups:
            painter.setPen(INK_SOFT)
            painter.drawText(self.rect(), int(Qt.AlignCenter), 'No findings to place.')
            return
        start = min((group.start for group in self.groups if group.start), default=None)
        end = max((group.end for group in self.groups if group.end), default=None)
        self.unplaced = sum(1 for group in self.groups if group.start is None)
        if start is None:
            painter.setPen(INK_SOFT)
            painter.drawText(self.rect(), int(Qt.AlignCenter), 'None of the findings carries a timestamp.')
            return
        if end is None or end <= start:
            end = start + timedelta(minutes=5)
        span = max(1.0, (end - start).total_seconds())
        hosts = []
        for group in self.groups:
            if group.host not in hosts:
                hosts.append(group.host)
        hosts = hosts[:6]
        area = QRectF(70, 48, self.width() - 82, self.height() - 76)
        lane_h = area.height() / max(1, len(hosts))
        font = QFont(self.font())
        font.setPointSizeF(max(7.0, font.pointSizeF() - 2.0))
        painter.setFont(font)
        for lane, host in enumerate(hosts):
            y = area.top() + lane_h * (lane + .5)
            painter.setPen(QPen(QColor('#22314a'), 1))
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            painter.setPen(INK_SOFT)
            painter.drawText(QRectF(4, y - 8, 62, 16), int(Qt.AlignRight | Qt.AlignVCenter), host[:14] or 'unknown')
        points = []
        for group in self.groups:
            if group.start is None or group.host not in hosts:
                continue
            x = area.left() + area.width() * (group.start - start).total_seconds() / span
            y = area.top() + lane_h * (hosts.index(group.host) + .5)
            colour = LEVEL_COLOURS.get(group.level, LEVEL_COLOURS['informational'])
            size = 5.0 + min(6.0, math.log1p(group.count))
            point = QPointF(x, y)
            points.append(point)
            if group.key == self.selected_key:
                painter.setPen(QPen(QColor('#ffffff'), 1.4))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(point, size + 5, size + 5)
            painter.setPen(Qt.NoPen)
            painter.setBrush(colour)
            painter.drawEllipse(point, size, size)
            self._marks.append((QRectF(x - size - 2, y - size - 2, size * 2 + 4, size * 2 + 4), group.key))
        if len(points) > 1:
            painter.setPen(QPen(QColor('#3d5170'), 1, Qt.DashLine))
            for left, right in zip(points, points[1:]):
                painter.drawLine(left, right)
        painter.setPen(INK_FAINT)
        for tick in range(0, 5):
            x = area.left() + area.width() * tick / 4
            moment = start + timedelta(seconds=span * tick / 4)
            painter.drawText(QRectF(x - 40, area.bottom() + 4, 80, 16), int(Qt.AlignCenter),
                             moment.strftime('%H:%M:%S'))
