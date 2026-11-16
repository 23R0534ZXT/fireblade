"""Startup ident: the wordmark is the mark.

Two attempts pasted or drew a flame, and both read as clip art: a low-resolution film
with visible seams, then vector tongues that looked like a feather. The name already
carries the idea, so the ident lets typography do the work — a centred wordmark, a
hairline above it, a warm light behind it, and dust that drifts rather than sparks that
fizz. What it must not do is look like a placeholder.

Nothing here is random: every ember and every flicker is a function of the phase, so the
ident is identical on every launch and can be captured frame by frame in a test.
"""
import math

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import (QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
                           QRadialGradient)
from PySide6.QtWidgets import QWidget

from fireblade import __version__

WIDTH, HEIGHT = 720, 400
CENTRE = WIDTH / 2

BACKDROP = QColor('#050608')
TITLE = QColor('#f6f3ee')
MUTED = QColor('#a8a49c')
FAINT = QColor('#5f6369')
AMBER = QColor('#f2ab6b')

# One clock for the whole ident; every move is a window on it, so the cadence can be
# retuned in one place. Long enough to breathe, short enough not to stand between the
# analyst and the work.
DURATION = 6500


def ease(value):
    """Smoothstep: monotonic, cheap, and it never overshoots its brackets."""
    value = min(1.0, max(0.0, value))
    return value * value * (3 - 2 * value)


def out(value):
    """Ease out: fast at the start, settling — what a lit object does."""
    value = min(1.0, max(0.0, value))
    return 1 - (1 - value) ** 3


def window(phase, start, length):
    """Progress of a sub-move, in fractions of the ident: 0 before it, 1 after it."""
    if length <= 0:
        return float(phase >= start)
    return min(1.0, max(0.0, (phase - start) / length))


class StartupAnimation(QWidget):
    finished = Signal()

    def __init__(self):
        super().__init__(None, Qt.SplashScreen | Qt.FramelessWindowHint)
        self.setWindowTitle('Fireblade')
        self.setFixedSize(WIDTH, HEIGHT)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.phase = 0.0
        self.animation = QVariantAnimation(self)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setDuration(DURATION)
        # Linear on purpose: the easing belongs to each move, not to the clock.
        self.animation.setEasingCurve(QEasingCurve.Linear)
        self.animation.valueChanged.connect(self.advance)
        self.animation.finished.connect(self.finished.emit)
        screen = self.screen().availableGeometry()
        self.move(screen.center() - self.rect().center())

    def advance(self, value):
        self.phase = value
        self.update()

    def closeEvent(self, event):
        self.animation.stop()
        super().closeEvent(event)

    # ------------------------------------------------------------------ painting

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.fillRect(self.rect(), BACKDROP)
        heat = ease(window(self.phase, .00, .32))
        self.paint_light(painter, heat)
        self.paint_dust(painter, heat)
        self.paint_wordmark(painter)
        self.paint_progress(painter, heat)
        self.paint_exit(painter)

    def glow(self, painter, centre, size, colours):
        """A radial glow that is elliptical on purpose: a circular one leaves a rim."""
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        painter.setPen(Qt.NoPen)
        painter.translate(centre)
        painter.scale(size[0], size[1])
        gradient = QRadialGradient(QPointF(0, 0), 1.0)
        for stop, colour in colours:
            gradient.setColorAt(stop, colour)
        painter.setBrush(gradient)
        painter.drawEllipse(QRectF(-1, -1, 2, 2))
        painter.restore()

    def paint_light(self, painter, heat):
        """Warm light behind the wordmark, and a vignette that shapes the eye."""
        breath = .5 + .5 * math.sin(self.phase * math.tau * 1.05)
        self.glow(painter, QPointF(CENTRE, 210), (440, 262),
                  [(0.0, QColor(232, 126, 56, int(38 * heat))),
                   (0.42, QColor(150, 62, 22, int(16 * heat))),
                   (1.0, QColor(60, 20, 8, 0))])
        self.glow(painter, QPointF(CENTRE, 218), (250, 132),
                  [(0.0, QColor(255, 186, 118, int((30 + 10 * breath) * heat))),
                   (1.0, QColor(255, 140, 70, 0))])
        vignette = QRadialGradient(QPointF(CENTRE, 200), 470)
        vignette.setColorAt(.40, QColor(0, 0, 0, 0))
        vignette.setColorAt(1, QColor(0, 0, 0, 188))
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.fillRect(self.rect(), vignette)
        painter.restore()

    def paint_dust(self, painter, heat):
        """Deterministic motes: dust in warm light, not a fireworks display."""
        if heat <= 0:
            return
        painter.setPen(Qt.NoPen)
        for index in range(22):
            rate = .55 + .22 * ((index * 5) % 4) / 3
            age = (self.phase * rate + index * .083) % 1
            drift = math.sin(index * 1.9 + age * 4.2) * (26 + index % 5 * 14)
            x = CENTRE + drift * (.6 + .5 * age)
            y = 330 - age * (250 + index % 4 * 26)
            size = .8 + (index % 4) * .55
            alpha = heat * math.sin(age * math.pi) ** 2 * (26 + index % 3 * 14)
            painter.setBrush(QColor(255, 186, 122, int(alpha)))
            painter.drawEllipse(QRectF(x, y, size, size))

    def wordmark_font(self):
        font = QFont('Segoe UI', 31, QFont.DemiBold)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 9.0)
        return font

    def paint_wordmark(self, painter):
        """Hairline, letters, light sweep, rule, tagline, version — one centred axis."""
        font = self.wordmark_font()
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text = 'FIREBLADE'
        advance = [metrics.horizontalAdvance(letter) + 9.0 for letter in text]
        total = sum(advance) - 9.0
        left = CENTRE - total / 2
        base = 228.0

        x = left
        for index, letter in enumerate(text):
            local = ease(window(self.phase, .16 + index * .034, .24))
            if local > 0:
                painter.save()
                painter.setOpacity(local)
                painter.setPen(TITLE)
                painter.drawText(QPointF(x, base - 10 * (1 - local)), letter)
                painter.restore()
            x += advance[index]

        sweep = window(self.phase, .54, .22)
        if 0 < sweep < 1:
            glyphs = QPainterPath()
            glyphs.addText(QPointF(left, base), font, text)
            band = QRectF(left + sweep * (total + 190) - 95, base - 36, 95, 50)
            sheen = QLinearGradient(band.topLeft(), band.topRight())
            sheen.setColorAt(0, QColor(255, 214, 170, 0))
            sheen.setColorAt(.5, QColor(255, 240, 212, 104))
            sheen.setColorAt(1, QColor(255, 214, 170, 0))
            painter.save()
            painter.setClipPath(glyphs)
            painter.setCompositionMode(QPainter.CompositionMode_Plus)
            painter.fillRect(band, sheen)
            painter.restore()

        marker = out(window(self.phase, .44, .18))
        if marker > 0:
            width = 64 * marker
            painter.setPen(QPen(QColor(AMBER.red(), AMBER.green(), AMBER.blue(), int(205 * marker)), 1.6))
            painter.drawLine(QPointF(CENTRE - width / 2, 254), QPointF(CENTRE + width / 2, 254))

        tagline = ease(window(self.phase, .50, .20))
        if tagline > 0:
            painter.save()
            painter.setOpacity(tagline)
            font = QFont('Segoe UI', 8)
            font.setLetterSpacing(QFont.AbsoluteSpacing, 3.6)
            painter.setFont(font)
            painter.setPen(MUTED)
            painter.drawText(QRectF(0, 272 + 6 * (1 - tagline), WIDTH, 24),
                             Qt.AlignHCenter | Qt.AlignVCenter, 'INVESTIGATION NUMÉRIQUE')
            painter.restore()

        stamp = ease(window(self.phase, .60, .16))
        if stamp > 0:
            painter.save()
            painter.setOpacity(stamp * .92)
            font = QFont('Segoe UI', 7)
            font.setLetterSpacing(QFont.AbsoluteSpacing, 1.7)
            painter.setFont(font)
            painter.setPen(FAINT)
            painter.drawText(QRectF(0, 300, WIDTH, 20), Qt.AlignHCenter | Qt.AlignVCenter,
                             'VERSION ' + __version__ + '   ·   DFIR')
            painter.restore()

    def paint_progress(self, painter, heat):
        """A hairline that fills: an ident with no signal feels frozen."""
        track = QRectF(96, 392, WIDTH - 192, 1.2)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, int(12 * heat)))
        painter.drawRoundedRect(track, .6, .6)
        filled = track.width() * out(window(self.phase, .03, .88))
        if filled <= 0:
            return
        bar = QRectF(track.left(), track.top(), filled, track.height())
        fill = QLinearGradient(bar.topLeft(), bar.topRight())
        fill.setColorAt(0, QColor(148, 54, 18, 140))
        fill.setColorAt(.72, QColor(224, 148, 92, 195))
        fill.setColorAt(1, QColor(255, 210, 160, 225))
        painter.setBrush(fill)
        painter.drawRoundedRect(bar, .6, .6)
        head = QRadialGradient(QPointF(bar.right(), bar.center().y()), 9)
        head.setColorAt(0, QColor(255, 214, 170, int(110 * heat)))
        head.setColorAt(1, QColor(226, 128, 62, 0))
        painter.setBrush(head)
        painter.drawEllipse(QRectF(bar.right() - 9, bar.center().y() - 4, 18, 8))

    def paint_exit(self, painter):
        """Fade out, so the window appears out of the dark instead of on top of it."""
        fade = window(self.phase, .94, .06)
        if fade > 0:
            painter.fillRect(self.rect(), QColor(5, 6, 8, int(255 * ease(fade))))
