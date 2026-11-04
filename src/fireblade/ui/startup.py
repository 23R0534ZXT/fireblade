"""Ten-second cinematic ident, decoded one frame at a time without a video runtime."""
import math

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QMovie, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from fireblade import __version__
from fireblade.runtime.resources import resource_path


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
        self.animation.setEasingCurve(QEasingCurve.Linear)
        self.animation.valueChanged.connect(self.advance)
        self.animation.stateChanged.connect(self.animation_state)
        self.animation.finished.connect(self.finished.emit)
        screen = self.screen().availableGeometry()
        self.move(screen.center()-self.rect().center())

    def animation_state(self, state, previous):
        if state == QAbstractAnimation.Running:self.movie.start()
        else:self.movie.stop()

    def advance(self, value):
        self.phase = value
        # The film supplies the paint cadence (20 fps), including the text fade.
        if self.movie.state() != QMovie.Running or value == 1.0:self.update()

    def closeEvent(self, event):
        self.animation.stop(); self.movie.stop()
        super().closeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor('#030405'))
        heat = min(1.0, max(0.0, (self.phase-.035)/.32))
        heat = heat*heat*(3-2*heat)
        glow = QRadialGradient(508, 260, 260)
        glow.setColorAt(0, QColor(158, 62, 17, int(30*heat)))
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), glow)
        frame = self.movie.currentPixmap()
        if not frame.isNull():
            painter.save()
            # The light rises from the coals before revealing the full flame.
            rise = min(1.0, max(0.0, self.phase/.34))
            painter.setClipRect(QRectF(338, 400-430*rise, 342, 430*rise))
            painter.setOpacity(heat)
            painter.drawPixmap(QRectF(340, -20, 320, 426), frame, QRectF(frame.rect()))
            painter.restore()
            edge = QLinearGradient(338, 0, 420, 0)
            edge.setColorAt(0, QColor('#030405')); edge.setColorAt(1, QColor(3, 4, 5, 0))
            painter.fillRect(QRectF(338, 0, 85, 400), edge)
            edge = QLinearGradient(0, 300, 0, 400)
            edge.setColorAt(0, QColor(3, 4, 5, 0)); edge.setColorAt(1, QColor('#030405'))
            painter.fillRect(QRectF(335, 300, 345, 100), edge)
        # A few close embers give depth while staying cheap to paint.
        for i in range(12):
            age = (self.phase*1.7+i*.1337)%1
            x = 455+math.sin(i*4+age*5)*75
            y = 325-age*290
            painter.setPen(Qt.NoPen); painter.setBrush(QColor(255, 160, 78, int(heat*(1-age)**2*100)))
            painter.drawEllipse(QRectF(x, y, 1, 2.5))
        reveal = min(1.0, max(0.0, (self.phase-.18)/.28))
        reveal = 1-(1-reveal)**3
        painter.save(); painter.setOpacity(reveal)
        painter.translate(0, 8*(1-reveal))
        painter.setPen(QPen(QColor('#d68c54'), 2)); painter.drawLine(48, 136, 77, 136)
        font = QFont('Segoe UI', 27, QFont.DemiBold); font.setLetterSpacing(QFont.AbsoluteSpacing, 2.7)
        painter.setFont(font); painter.setPen(QColor('#f1eee9'))
        painter.drawText(QRectF(45, 157, 310, 58), Qt.AlignLeft | Qt.AlignVCenter, 'FIREBLADE')
        font = QFont('Segoe UI', 8); font.setLetterSpacing(QFont.AbsoluteSpacing, 1.7)
        painter.setFont(font); painter.setPen(QColor('#8d8983'))
        painter.drawText(QRectF(48, 221, 290, 25), Qt.AlignLeft | Qt.AlignVCenter, 'INVESTIGATION NUMÉRIQUE')
        painter.restore()
        painter.setFont(QFont('Segoe UI', 8)); painter.setPen(QColor('#575b61'))
        painter.drawText(QRectF(48, 350, 200, 22), Qt.AlignLeft | Qt.AlignVCenter, __version__)
        painter.setPen(QPen(QColor('#1b1c1e'), 1)); painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
