"""Three maps of a finding set, drawn in the application's own palette.

They are plain ``QWidget`` subclasses painting with ``QPainter``: no charting dependency,
no QtQuick, and every mark is a function of the data, so the same findings always give the
same picture — which is what makes a capture in a test mean something.

The colours come from the widget's palette (white base, #202020 text) and match the
severity colours the rest of the window uses; there is no dark canvas and no glow, because
the rest of Fireblade is a light, thin-lined workspace.

Each map emits ``group_selected(index)`` when the analyst clicks a mark, and exposes
``set_data(groups, incidents)`` and ``select(key)``. Whatever they cannot draw — a group
with no timestamp — they count and report through ``unplaced()`` instead of hiding it.
"""
from __future__ import annotations

import math
from datetime import timedelta

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPainterPathStroker, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

# Severity colours: readable on white, distinct without being fluorescent.
LEVEL_COLOURS = {
    'critical': QColor('#6d130d'),
    'high': QColor('#b3261e'),
    'medium': QColor('#a06a00'),
    'low': QColor('#5c7a3a'),
    'informational': QColor('#8a8a8a'),
}
BAND = QColor('#cce8ff')
EDGE = QColor('#4c86c6')
RANKS = {'informational': 1, 'low': 2, 'medium': 3, 'high': 4, 'critical': 5}


class FindingMap(QWidget):
    """Common behaviour: data, selection, hit-testing and an honest 'not drawn' count."""

    group_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.groups = []
        self.incidents = []
        self.selected_key = ''
        self._marks = []          # (QRectF, key)
        self.unplaced = 0
        self.setMinimumHeight(120)
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
        key = self.mark_at(event.position())
        if key is not None:
            self.selected_key = key
            index = next((i for i, group in enumerate(self.groups) if group.key == key), -1)
            if index >= 0:
                self.group_selected.emit(index)
            self.update()
            return
        super().mousePressEvent(event)

    def mark_at(self, position):
        """What is under the pointer: the drawing decides, not a rectangle around its tip.

        A ray is four pixels wide, so its bounding box was the only thing that could be
        clicked and the tip was a sixteen-pixel square: the line itself ignored the click.
        Marks now carry the shape they drew, which is a stroked segment for a ray.
        """
        for shape, key in reversed(self._marks):
            if shape.contains(position):
                return key
        return None

    def mouseMoveEvent(self, event):
        key = self.mark_at(event.position())
        group = next((item for item in self.groups if item.key == key), None) if key else None
        self.setToolTip('%s · %s' % (group.level, group.title) if group is not None else '')
        super().mouseMoveEvent(event)

    def colours(self):
        """Every colour the drawings need, taken from the widget's own palette.

        The window can be light or dark (Preferences); hard-coded light greys on a dark
        canvas made the dial nearly invisible, which is exactly what a screenshot caught.
        """
        palette = self.palette()
        base = palette.base().color()
        dark = base.lightness() < 128
        text = palette.text().color()
        mix = lambda colour, weight: QColor(
            int(colour.red() * weight + base.red() * (1 - weight)),
            int(colour.green() * weight + base.green() * (1 - weight)),
            int(colour.blue() * weight + base.blue() * (1 - weight)))
        return dict(
            base=base, ink=text,
            dim=mix(QColor('#808080') if dark else QColor('#686868'), .8),
            faint=mix(QColor('#c0c0c0') if dark else QColor('#b0b0b0'), .75),
            grid=mix(QColor('#3a3a3a') if dark else QColor('#e6e6e6'), 1.0),
            axis=mix(QColor('#5a5a5a') if dark else QColor('#b5b5b5'), 1.0),
            band=QColor('#315b7d') if dark else BAND,
            edge=QColor('#80bfff') if dark else EDGE,
            warn=QColor('#e0b050') if dark else QColor('#a06a00'),
        )

    def font_at(self, painter, size, bold=False):
        font = QFont(self.font())
        font.setPointSizeF(max(6.5, size))
        font.setBold(bold)
        painter.setFont(font)

    def paint_shell(self, painter, title, subtitle):
        """White canvas, one sentence at the top, and the count of what could not be drawn."""
        colours = self.colours()
        painter.fillRect(self.rect(), colours['base'])
        painter.setPen(colours['ink'])
        self.font_at(painter, self.font().pointSizeF())
        painter.drawText(QRectF(10, 4, self.width() - 20, 18), int(Qt.AlignLeft | Qt.AlignVCenter), title)
        painter.setPen(colours['dim'])
        self.font_at(painter, self.font().pointSizeF() - 1.5)
        painter.drawText(QRectF(10, 20, self.width() - 20, 16), int(Qt.AlignLeft | Qt.AlignVCenter), subtitle)
        if self.unplaced:
            painter.setPen(colours['warn'])
            painter.drawText(QRectF(10, self.height() - 18, self.width() - 20, 14),
                             int(Qt.AlignRight | Qt.AlignVCenter),
                             '%d finding(s) without a usable timestamp are not drawn' % self.unplaced)


class CircularMap(FindingMap):
    """The day as a polar histogram: angle = time, ray length = alerts, colour = severity.

    A dial of dots reads as decoration and hides the volume. Rays read as a measurement:
    the quiet hours are short ticks, the incident is a spike, and the eye finds it without
    a legend. One ray per ten minutes; its colour is the worst severity in that slice.
    """

    BINS = 144
    RINGS = (5, 10, 15)

    def _day(self):
        dated = [group for group in self.groups if group.start is not None]
        if not dated:
            return None, []
        day_start = min(group.start for group in dated).replace(hour=0, minute=0, second=0, microsecond=0)
        return day_start, dated

    def _bins(self, day_start, dated):
        size = 24 * 60 / self.BINS
        bins = [dict(count=0, level=None, owner=None) for _ in range(self.BINS)]
        for group in dated:
            index = min(self.BINS - 1,
                        int(((group.start - day_start).total_seconds() / 60) // size))
            bins[index]['count'] += group.count
            if bins[index]['level'] is None or RANKS[group.level] > RANKS[bins[index]['level']]:
                bins[index]['level'] = group.level
            if bins[index]['owner'] is None or RANKS[group.level] > RANKS[bins[index]['level']]:
                # The slice is one click target: it must open the worst thing in it.
                bins[index]['owner'] = group.key
        return bins

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self._marks = []
        colours = self.colours()
        self.paint_shell(painter, 'The day',
                         'angle = time of day - one ray per ten minutes - length = alerts in it')
        if not self.groups:
            painter.setPen(colours['dim'])
            painter.drawText(self.rect(), int(Qt.AlignCenter), 'No findings to place.')
            return
        area = QRectF(10, 38, self.width() - 20, self.height() - 62)
        centre = QPointF(area.center())
        outer = min(area.width(), area.height()) / 2 - 24
        inner = max(34.0, outer * .32)
        if outer <= inner + 20:
            return
        day_start, dated = self._day()
        self.unplaced = len(self.groups) - len(dated)
        if day_start is None:
            painter.setPen(colours['dim'])
            painter.drawText(self.rect(), int(Qt.AlignCenter), 'None of the findings carries a timestamp.')
            return
        bins = self._bins(day_start, dated)
        peak = max(1, max(item['count'] for item in bins))
        step = 360.0 / self.BINS
        angle_of = lambda index: math.radians(index * step - 90 + step / 2)

        painter.setBrush(Qt.NoBrush)
        for value in self.RINGS:
            radius = inner + (outer - inner) * min(1.0, value / max(peak, self.RINGS[-1]))
            painter.setPen(QPen(colours['grid'], 1))
            painter.drawEllipse(centre, radius, radius)
            painter.setPen(colours['faint'])
            self.font_at(painter, 7.5)
            painter.drawText(QPointF(centre.x() + 4, centre.y() - radius - 3), str(value))

        for index, item in enumerate(bins):
            if not item['count']:
                continue
            angle = angle_of(index)
            length = (outer - inner) * min(1.0, item['count'] / peak)
            painter.setPen(QPen(LEVEL_COLOURS.get(item['level'], LEVEL_COLOURS['informational']),
                                4.0, Qt.SolidLine, Qt.FlatCap))
            painter.drawLine(QPointF(centre.x() + math.cos(angle) * inner,
                                     centre.y() + math.sin(angle) * inner),
                             QPointF(centre.x() + math.cos(angle) * (inner + length),
                                     centre.y() + math.sin(angle) * (inner + length)))

        painter.setPen(QPen(colours['axis'], 1))
        for hour in range(0, 24, 3):
            angle = math.radians(hour * 15 - 90)
            painter.drawLine(QPointF(centre.x() + math.cos(angle) * outer, centre.y() + math.sin(angle) * outer),
                             QPointF(centre.x() + math.cos(angle) * (outer + 7),
                                     centre.y() + math.sin(angle) * (outer + 7)))
            painter.setPen(colours['dim'])
            self.font_at(painter, 7.5)
            painter.drawText(QRectF(centre.x() + math.cos(angle) * (outer + 12) - 22,
                                    centre.y() + math.sin(angle) * (outer + 12) - 8, 44, 16),
                             int(Qt.AlignCenter), '%02d:00' % hour)
            painter.setPen(QPen(colours['axis'], 1))

        selected = next((group for group in self.groups if group.key == self.selected_key), None)
        if selected is not None and selected.start is not None:
            size = 24 * 60 / self.BINS
            first = int(((selected.start - day_start).total_seconds() / 60) // size)
            last = max(first, int((((selected.end or selected.start) - day_start).total_seconds() / 60) // size))
            self._wedge(painter, centre, inner, outer, first, last, colours)

        # The summary sits in the middle only when the hole is wide enough for it; on a
        # short panel it used to spill over the rays, so it moves under the dial instead.
        summary = [dated[0].host or 'all hosts', day_start.strftime('%Y-%m-%d'),
                   '%d findings' % len(self.groups)]
        if inner >= 58:
            rows = [(centre.y() - 22, summary[0], True), (centre.y() - 4, summary[1], False),
                    (centre.y() + 12, summary[2], False)]
            for top, text, bold in rows:
                painter.setPen(colours['ink'] if bold else colours['dim'])
                self.font_at(painter, self.font().pointSizeF() + (1.0 if bold else -1.0), bold=bold)
                painter.drawText(QRectF(centre.x() - inner + 4, top, inner * 2 - 8, 16),
                                 int(Qt.AlignCenter), text)
        else:
            painter.setPen(colours['ink'])
            self.font_at(painter, self.font().pointSizeF() - 0.5)
            painter.drawText(QRectF(area.left(), self.height() - 34, area.width(), 14),
                             int(Qt.AlignCenter), ' - '.join(summary))

        self._legend(painter, colours)
        for index, item in enumerate(bins):
            if not item['count'] or item['owner'] is None:
                continue
            angle = angle_of(index)
            length = (outer - inner) * min(1.0, item['count'] / peak)
            start = QPointF(centre.x() + math.cos(angle) * inner,
                            centre.y() + math.sin(angle) * inner)
            tip = QPointF(centre.x() + math.cos(angle) * (inner + length),
                          centre.y() + math.sin(angle) * (inner + length))
            self._marks.append((self.ray_area(start, tip), item['owner']))

    def ray_area(self, start, tip):
        """The whole ray, eighteen pixels wide: a click anywhere along it selects it."""
        path = QPainterPath(start)
        path.lineTo(tip)
        stroker = QPainterPathStroker()
        stroker.setWidth(18)
        return stroker.createStroke(path)

    def _wedge(self, painter, centre, inner, outer, first, last, colours):
        """A pale sector from the first to the last slice of the selection.

        Built as a polygon rather than with ``arcTo``: the angle conventions of Qt arcs
        made a one-line version draw the band on the wrong side of the dial.
        """
        step = 360.0 / self.BINS
        path = QPainterPath()
        edges = []
        for index in range(first, last + 2):
            angle = math.radians((index * step) - 90)
            edges.append(angle)
        path.moveTo(QPointF(centre.x() + math.cos(edges[0]) * inner, centre.y() + math.sin(edges[0]) * inner))
        for angle in edges:
            path.lineTo(QPointF(centre.x() + math.cos(angle) * outer, centre.y() + math.sin(angle) * outer))
        for angle in reversed(edges):
            path.lineTo(QPointF(centre.x() + math.cos(angle) * inner, centre.y() + math.sin(angle) * inner))
        path.closeSubpath()
        painter.setPen(QPen(colours['edge'], 1))
        painter.setBrush(QBrush(colours['band']))
        painter.drawPath(path)
        painter.setBrush(Qt.NoBrush)

    def _legend(self, painter, colours):
        painter.setPen(colours['dim'])
        self.font_at(painter, 7.5)
        x = self.width() - 10
        for level in ('critical', 'high', 'medium', 'low', 'informational'):
            width = painter.fontMetrics().horizontalAdvance(level) + 14
            x -= width
            painter.setPen(Qt.NoPen)
            painter.setBrush(LEVEL_COLOURS[level])
            painter.drawEllipse(QPointF(x + 4, 30), 3.5, 3.5)
            painter.setPen(colours['dim'])
            painter.drawText(QRectF(x + 10, 23, width, 14), int(Qt.AlignLeft | Qt.AlignVCenter), level)
            x -= 6


class HeatMap(FindingMap):
    """One row per rule, one column per time slice: the grid the application already draws."""

    BUCKETS = 96

    def paintEvent(self, _event):
        painter = QPainter(self)
        self._marks = []
        colours = self.colours()
        self.paint_shell(painter, 'Rules over time',
                         'one row per rule - one column per fifteen minutes - shade = alerts')
        if not self.groups:
            painter.setPen(colours['dim'])
            painter.drawText(self.rect(), int(Qt.AlignCenter), 'No findings to place.')
            return
        dated = [group for group in self.groups if group.start is not None]
        self.unplaced = len(self.groups) - len(dated)
        if not dated:
            painter.setPen(colours['dim'])
            painter.drawText(self.rect(), int(Qt.AlignCenter), 'None of the findings carries a timestamp.')
            return
        start = min(group.start for group in dated)
        end = max((group.end or group.start) for group in dated)
        if end <= start:
            end = start + timedelta(hours=1)
        span = max(1.0, (end - start).total_seconds())
        label_width = min(280, max(140, self.width() // 3))
        area = QRectF(label_width, 46, self.width() - label_width - 12, self.height() - 74)
        rows = max(1, min(len(dated), int(area.height() // 18)))
        stride = max(1, len(dated) // rows)
        shown = dated[::stride][:rows]
        cell_h = area.height() / max(1, len(shown))
        cell_w = area.width() / self.BUCKETS
        self.font_at(painter, max(7.0, self.font().pointSizeF() - 1.0))
        for row, group in enumerate(shown):
            if row % 2 == 0:
                painter.fillRect(QRectF(4, area.top() + row * cell_h, area.right() - 4, cell_h),
                                 QColor('#fafafa'))
            column = min(self.BUCKETS - 1,
                         int(((group.start - start).total_seconds() / span) * self.BUCKETS))
            colour = LEVEL_COLOURS.get(group.level, LEVEL_COLOURS['informational'])
            shade = QColor(colour)
            shade.setAlphaF(0.20 + 0.70 * min(1.0, math.log1p(group.count) / 3.0))
            cell = QRectF(area.left() + column * cell_w, area.top() + row * cell_h + 1,
                          max(2.0, cell_w - 1), cell_h - 2)
            painter.fillRect(cell, shade)
            painter.setPen(QPen(QColor('#ffffff'), .5))
            painter.drawRect(cell)
            painter.setPen(QColor('#3a3a3a'))
            painter.drawText(QRectF(8, cell.top(), label_width - 34, cell_h),
                             int(Qt.AlignLeft | Qt.AlignVCenter), group.title[:44])
            painter.setPen(colours['dim'])
            painter.drawText(QRectF(area.left() - 30, cell.top(), 26, cell_h),
                             int(Qt.AlignRight | Qt.AlignVCenter), 'x%d' % group.count)
            self._marks.append((QRectF(area.left(), cell.top(), area.width(), cell_h), group.key))
        painter.setPen(colours['faint'])
        for tick in range(0, 5):
            x = area.left() + area.width() * tick / 4
            moment = start + timedelta(seconds=span * tick / 4)
            painter.drawText(QRectF(x - 40, area.bottom() + 4, 80, 14), int(Qt.AlignCenter),
                             moment.strftime('%d %H:%M'))


class ChainMap(FindingMap):
    """The events of the selected finding, and the links the assistant asserted.

    Two states, and the caption says which: before an explanation the points are in order
    and nothing is claimed; after it, every link the model asserted is drawn as an arrow
    labelled with the events it joins. A link whose end is not in the pack never reaches
    this widget, because ``core.explain.read_answer`` removed it.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.facts = []
        self.links = []

    def set_pack(self, pack):
        self.facts = list(getattr(pack, 'facts', []) or [])
        self.links = list(getattr(pack, 'links', []) or [])
        self.update()

    def _points(self, area):
        if not self.facts:
            return {}
        step = area.width() / max(1, len(self.facts))
        sources = []
        for row in self.facts:
            if row.source not in sources:
                sources.append(row.source)
        lanes = max(1, min(4, len(sources)))
        lane_of = {name: index % lanes for index, name in enumerate(sources)}
        lane_h = area.height() / lanes
        return {row.number: QPointF(area.left() + step * (index + .5),
                                    area.top() + lane_h * (lane_of.get(row.source, 0) + .5))
                for index, row in enumerate(self.facts)}

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self._marks = []
        colours = self.colours()
        caption = ('links asserted by the local assistant' if self.links else
                   'the events of this finding, in order - no link asserted yet')
        self.paint_shell(painter, 'The chain', caption)
        area = QRectF(60, 52, self.width() - 74, self.height() - 86)
        points = self._points(area)
        if not points:
            painter.setPen(colours['dim'])
            painter.drawText(self.rect(), int(Qt.AlignCenter), 'Select a finding first.')
            return
        lanes = sorted({round(point.y()) for point in points.values()})
        painter.setPen(QPen(colours['grid'], 1))
        for y in lanes:
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
        if not self.links:
            painter.setPen(QPen(QColor('#dcdcdc'), 1, Qt.DashLine))
            ordered = [points[number] for number in sorted(points)]
            for left, right in zip(ordered, ordered[1:]):
                painter.drawLine(left, right)
        for link in self.links:
            source, target = points.get(link.get('source')), points.get(link.get('target'))
            if source is None or target is None:
                continue
            lift = 24.0
            path = QPainterPath(QPointF(source.x(), source.y() - lift))
            mid_x = (source.x() + target.x()) / 2
            path.quadTo(QPointF(mid_x, min(source.y(), target.y()) - lift - 16),
                        QPointF(target.x(), target.y() - lift))
            painter.setPen(QPen(colours['edge'], 1.4))
            painter.drawPath(path)
            end = QPointF(target.x(), target.y() - lift)
            painter.setBrush(colours['edge'])
            painter.setPen(Qt.NoPen)
            painter.drawPolygon([end, QPointF(end.x() - 6, end.y() - 3), QPointF(end.x() - 6, end.y() + 3)])
            painter.setBrush(Qt.NoBrush)
            self.font_at(painter, 7.5)
            painter.setPen(colours['edge'])
            painter.drawText(QPointF(mid_x - 8, min(source.y(), target.y()) - lift - 6),
                             '%d-%d' % (link['source'], link['target']))
        for row in self.facts:
            point = points[row.number]
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor('#2f5f96'))
            painter.drawEllipse(point, 5, 5)
            painter.setPen(QColor('#3a3a3a'))
            self.font_at(painter, 7.5)
            painter.drawText(QPointF(point.x() - 3, point.y() - 9), str(row.number))
            painter.setPen(colours['dim'])
            painter.drawText(QPointF(point.x() - 20, point.y() + 18), row.stamp[-8:])
            self._marks.append((QRectF(point.x() - 8, point.y() - 8, 16, 16), row.number))
