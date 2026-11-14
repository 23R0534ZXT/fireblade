"""Ten-second cinematic ident, decoded one frame at a time without a video runtime."""
import math

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import (QColor, QFont, QLinearGradient, QMovie, QPainter, QPainterPath,
                           QPen, QRadialGradient)
from PySide6.QtWidgets import QWidget

from fireblade import __version__
from fireblade.runtime.resources import resource_path

EMBER = '#d68c54'
AMBER = '#f4b072'
TITLE = '#f4f1ec'
MUTED = '#9d998f'
FAINT = '#575b61'
BACKDROP = '#030405'


def ease(value):
    """Smoothstep: cheap, monotonic, and it never overshoots the brackets."""
    value = min(1.0, max(0.0, value))
    return value * value * (3 - 2 * value)


def window(phase, start, length):
    """Progress of a sub-move, 0 before it, 1 after it."""
    return min(1.0, max(0.0, (phase - start) / length)) if length > 0 else float(phase >= start)


class StartupAnimation(QWidget):
    finished = Signal()

    def __init__(self):
        super().__init__(None, Qt.SplashScreen | Qt.FramelessWindowHint)
        self.setWindowTitle('Fireblade')
        self.setFixedSize(680, 400)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.phase = 0.0
        self.movie = QMovie(str(resource_path('assets/startup/fire.gif')), parent=self)
        self.movie.setCacheMode(QMovie.CacheNone)
        self.movie.frameChanged.connect(lambda _: self.update())
        self.movie.jumpToFrame(0)
        self.animation = QVariantAnimation(self)
        self.animation.setStartValue(0.0); self.animation.setEndValue(1.0)
        self.animation.setDuration(10000)
        # Linear on purpose: every move is timed against the absolute phase, so the
        # easing belongs to the move itself, not to the clock that drives it.
        self.animation.setEasingCurve(QEasingCurve.Linear)
        self.animation.valueChanged.connect(self.advance)
        self.animation.stateChanged.connect(self.animation_state)
        self.animation.finished.connect(self.finished.emit)
        screen = self.screen().availableGeometry()
        self.move(screen.center() - self.rect().center())

    def animation_state(self, state, previous):
        if state == QAbstractAnimation.Running:self.movie.start()
        else:self.movie.stop()

    def advance(self, value):
        self.phase = value
        # The ident drives its own cadence: the film is only 20 fps, and the glow,
        # the sweep and the progress line need to breathe faster than that.
        self.update()

    def closeEvent(self, event):
        self.animation.stop(); self.movie.stop()
        super().closeEvent(event)

    # ------------------------------------------------------------------ painting

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor(BACKDROP))
        heat = ease(window(self.phase, .035, .30))
        self.paint_backdrop(painter, heat)
        self.paint_fire(painter, heat)
        self.paint_embers(painter, heat)
        self.paint_ident(painter)
        self.paint_progress(painter, heat)
        self.paint_exit(painter)

    def paint_backdrop(self, painter, heat):
        """Two glows, offset in time, so the light feels alive instead of switched on."""
        breath = .5 + .5 * math.sin(self.phase * math.tau * 1.6)
        warm = QRadialGradient(QPointF(512, 262), 250 + 18 * breath)
        warm.setColorAt(0, QColor(168, 66, 18, int(34 * heat * (.9 + .1 * breath))))
        warm.setColorAt(.45, QColor(96, 34, 12, int(12 * heat)))
        warm.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), warm)
        halo = QRadialGradient(QPointF(430, 210), 330)
        halo.setColorAt(0, QColor(46, 34, 30, int(26 * heat)))
        halo.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), halo)
        # Vignette: pulls the eye to the flame and hides the pixmap edges.
        vignette = QRadialGradient(QPointF(340, 210), 470)
        vignette.setColorAt(.55, QColor(0, 0, 0, 0))
        vignette.setColorAt(1, QColor(0, 0, 0, 130))
        painter.fillRect(self.rect(), vignette)

    def paint_fire(self, painter, heat):
        frame = self.movie.currentPixmap()
        if frame.isNull():return
        rise = ease(window(self.phase, .0, .34))
        breathe = 1.0 + .012 * math.sin(self.phase * math.tau * 2.2) * heat
        target = QRectF(340, -20, 320 * breathe, 426 * breathe)
        if rise > 0:
            # The light rises from the coals, and the edge of the reveal must not show:
            # one clipped draw, then a dark gradient feathered over the cut, so the
            # flame appears out of the dark instead of out of a straight line.
            cut = 400 - 430 * rise
            painter.save()
            painter.setClipRect(QRectF(338, cut, 344, 430 * rise + 2))
            painter.setOpacity(heat)
            painter.drawPixmap(target, frame, QRectF(frame.rect()))
            painter.restore()
            if rise < 1:
                feather = QLinearGradient(0, cut, 0, cut + 60)
                feather.setColorAt(0, QColor(3, 4, 5, 255))
                feather.setColorAt(.55, QColor(3, 4, 5, 120))
                feather.setColorAt(1, QColor(3, 4, 5, 0))
                painter.fillRect(QRectF(338, cut, 344, 60), feather)
        # Soften all four sides so the film melts into the backdrop.
        edge = QLinearGradient(338, 0, 424, 0)
        edge.setColorAt(0, QColor(BACKDROP)); edge.setColorAt(1, QColor(3, 4, 5, 0))
        painter.fillRect(QRectF(338, 0, 86, 400), edge)
        edge = QLinearGradient(0, 296, 0, 400)
        edge.setColorAt(0, QColor(3, 4, 5, 0)); edge.setColorAt(1, QColor(BACKDROP))
        painter.fillRect(QRectF(334, 296, 348, 104), edge)
        edge = QLinearGradient(0, 0, 0, 46)
        edge.setColorAt(0, QColor(BACKDROP)); edge.setColorAt(1, QColor(3, 4, 5, 0))
        painter.fillRect(QRectF(334, 0, 348, 46), edge)

    def paint_embers(self, painter, heat):
        """Deterministic particles: no state to keep, no random to seed."""
        painter.setPen(Qt.NoPen)
        for index in range(18):
            age = (self.phase * (1.35 + .35 * ((index * 7) % 5) / 4) + index * .137) % 1
            drift = math.sin(index * 2.7 + age * 6.2) * (18 + index % 4 * 9)
            x = 500 + drift
            y = 330 - age * (250 + index % 6 * 22)
            size = .9 + (index % 5) * .45
            alpha = heat * (1 - age) ** 2 * (70 + index % 3 * 30)
            painter.setBrush(QColor(255, 168, 84, int(alpha)))
            painter.drawEllipse(QRectF(x, y, size, size * 2.1))
        # A handful of sparks with a short trail read as depth without costing much.
        painter.setPen(QPen(QColor(255, 206, 150, int(120 * heat)), .9))
        for index in range(5):
            age = (self.phase * 1.9 + index * .21) % 1
            x = 505 + math.sin(index * 3.1 + age * 4.4) * (24 + index * 6)
            y = 322 - age * 300
            painter.drawLine(QPointF(x, y), QPointF(x + .6, y + 5.5))

    def paint_ident(self, painter):
        """Letter by letter, then a light sweep across the wordmark."""
        letters = list('FIREBLADE')
        font = QFont('Segoe UI', 27, QFont.DemiBold)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 2.7)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        x = 46.0
        base = 186.0
        for index, letter in enumerate(letters):
            local = ease(window(self.phase, .16 + index * .035, .30))
            if local <= 0:continue
            painter.save()
            painter.setOpacity(local)
            painter.setPen(QColor(TITLE))
            painter.drawText(QPointF(x, base - 9 * (1 - local)), letter)
            painter.restore()
            x += metrics.horizontalAdvance(letter) + (2.7 if letter else 0)
        wordmark = QRectF(44, 150, x - 44, 46)
        sweep = window(self.phase, .52, .34)
        if 0 < sweep < 1:
            # The light must travel over the glyphs, not over a rectangle behind them:
            # clipping to the text path is what turns a grey slab into a sheen.
            glyphs = QPainterPath()
            glyphs.addText(QPointF(46, base), font, ''.join(letters))
            band = QRectF(wordmark.left() + sweep * (wordmark.width() + 120) - 60,
                          wordmark.top() - 6, 60, wordmark.height() + 12)
            sheen = QLinearGradient(band.topLeft(), band.topRight())
            sheen.setColorAt(0, QColor(255, 214, 170, 0))
            sheen.setColorAt(.5, QColor(255, 226, 190, 120))
            sheen.setColorAt(1, QColor(255, 214, 170, 0))
            painter.save()
            painter.setClipPath(glyphs)
            painter.setCompositionMode(QPainter.CompositionMode_Plus)
            painter.fillRect(band, sheen)
            painter.restore()
        # Hairline above the wordmark, drawn from the left as the letters appear.
        rule = ease(window(self.phase, .10, .28)) * 29
        if rule > 0:
            painter.setPen(QPen(QColor(EMBER), 2))
            painter.drawLine(QPointF(48, 136), QPointF(48 + rule, 136))
        subtitle = ease(window(self.phase, .40, .30))
        if subtitle > 0:
            painter.save()
            painter.setOpacity(subtitle)
            font = QFont('Segoe UI', 8); font.setLetterSpacing(QFont.AbsoluteSpacing, 1.9)
            painter.setFont(font); painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(48, 224 - 4 * (1 - subtitle), 290, 25),
                             Qt.AlignLeft | Qt.AlignVCenter, 'INVESTIGATION NUMÉRIQUE')
            painter.restore()
        stamp = ease(window(self.phase, .62, .26))
        if stamp > 0:
            painter.save()
            painter.setOpacity(stamp * .95)
            font = QFont('Segoe UI', 8); font.setLetterSpacing(QFont.AbsoluteSpacing, .8)
            painter.setFont(font); painter.setPen(QColor(FAINT))
            painter.drawText(QRectF(48, 350, 220, 22), Qt.AlignLeft | Qt.AlignVCenter,
                             'v' + __version__ + '   ·   DFIR')
            painter.restore()
        painter.setPen(QPen(QColor('#161718'), 1)); painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def paint_progress(self, painter, heat):
        """A hairline that fills, because an ident with no signal feels frozen."""
        track = QRectF(48, 376, 584, 1.2)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, int(14 * heat)))
        painter.drawRoundedRect(track, .6, .6)
        filled = track.width() * min(1.0, self.phase / .92)
        if filled <= 0:return
        bar = QRectF(track.left(), track.top(), filled, track.height())
        fill = QLinearGradient(bar.topLeft(), bar.topRight())
        fill.setColorAt(0, QColor(150, 52, 16, 170))
        fill.setColorAt(.7, QColor(214, 140, 84, 220))
        fill.setColorAt(1, QColor(255, 196, 140, 240))
        painter.setBrush(fill)
        painter.drawRoundedRect(bar, .6, .6)
        head = QRadialGradient(QPointF(bar.right(), bar.center().y()), 9)
        head.setColorAt(0, QColor(255, 198, 146, int(120 * heat)))
        head.setColorAt(.55, QColor(226, 128, 62, int(60 * heat)))
        head.setColorAt(1, QColor(200, 90, 40, 0))
        painter.setBrush(head)
        painter.drawEllipse(QRectF(bar.right() - 9, bar.center().y() - 4, 18, 8))

    def paint_exit(self, painter):
        """Fade to black so the main window appears out of the dark, not on top of it."""
        fade = window(self.phase, .94, .06)
        if fade > 0:
            painter.fillRect(self.rect(), QColor(3, 4, 5, int(255 * ease(fade))))
