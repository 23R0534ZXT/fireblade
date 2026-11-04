"""Draw literal matches without recoloring unrelated cells or complete rows."""
import re

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QTextCharFormat, QTextLayout


def match_ranges(text, terms):
    ranges = []
    for term in dict.fromkeys(term for term in terms if term):
        for match in re.finditer(re.escape(term), text, re.IGNORECASE):
            # QTextLayout addresses UTF-16 code units, Python indexes codepoints.
            start = len(text[:match.start()].encode('utf-16-le')) // 2
            length = len(match.group().encode('utf-16-le')) // 2
            ranges.append((start, length))
    return ranges


def paint_matches(painter, rect, text, font, foreground, alignment, terms):
    painter.save();painter.setClipRect(rect);painter.setPen(foreground)
    from PySide6.QtGui import QFontMetrics
    text = QFontMetrics(font).elidedText(text, Qt.ElideRight, rect.width())
    layout = QTextLayout(text, font)
    formats = []
    for start, length in match_ranges(text, terms):
        item = QTextLayout.FormatRange();item.start = start;item.length = length
        style = QTextCharFormat();style.setBackground(QColor('#f5cf65'));style.setForeground(QColor('#241c0b'))
        item.format = style;formats.append(item)
    layout.setFormats(formats);layout.beginLayout();line = layout.createLine()
    if line.isValid():
        line.setLineWidth(rect.width())
        x = rect.left()
        if alignment & Qt.AlignRight:x += max(0, rect.width()-line.naturalTextWidth())
        elif alignment & Qt.AlignHCenter:x += max(0, (rect.width()-line.naturalTextWidth())/2)
        layout.endLayout();layout.draw(painter, QPointF(x, rect.top()+(rect.height()-line.height())/2))
    else:layout.endLayout()
    painter.restore()
