"""Lightweight vector ident; animation remains optional and event driven."""
import math

from PySide6.QtCore import QEasingCurve, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget
from fireblade import __version__


class StartupAnimation(QWidget):
    finished = Signal()

    def __init__(self):
        super().__init__(None, Qt.SplashScreen | Qt.FramelessWindowHint)
        self.setWindowTitle('Fireblade')
        self.setFixedSize(560, 320)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.phase = 0.0
        self.animation = QVariantAnimation(self)
        self.animation.setStartValue(0.0); self.animation.setEndValue(1.0)
        self.animation.setDuration(4800)
        self.animation.setEasingCurve(QEasingCurve.Linear)
        self.animation.valueChanged.connect(self.advance)
        self.animation.finished.connect(self.finished.emit)
        screen = self.screen().availableGeometry()
        self.move(screen.center()-self.rect().center())

    def advance(self, value):
        self.phase = value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor('#0b1018'))
        glow = QRadialGradient(280, 112, 160)
        glow.setColorAt(0, QColor(217, 93, 41, 30)); glow.setColorAt(1, QColor(11, 16, 24, 0))
        painter.fillRect(self.rect(), glow)
        painter.setPen(QPen(QColor('#202a37'), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        # A faint technical grid; no video, bitmap frames or background workers.
        painter.setPen(QPen(QColor(135, 155, 182, 9), 1))
        for x in range(24, 560, 32):painter.drawLine(x, 24, x, 280)
        for y in range(24, 280, 32):painter.drawLine(24, y, 536, y)
        reveal = min(1.0, self.phase*4)
        reveal = 1-(1-reveal)**3
        painter.save()
        painter.translate(280, 108+8*(1-reveal))
        scale = .9+.1*reveal+.012*math.sin(self.phase*math.pi*4)*reveal
        painter.scale(scale, scale)
        flame = QPainterPath()
        flame.moveTo(0, -49); flame.cubicTo(9, -12, 46, -6, 30, 26)
        flame.cubicTo(14, 53, -33, 41, -32, 12)
        flame.cubicTo(-32, -6, -12, -16, -14, -30)
        flame.cubicTo(-8, -21, -4, -10, -4, -2)
        flame.cubicTo(9, -18, -5, -28, 0, -49)
        painter.setOpacity(reveal)
        gradient = QLinearGradient(0, -49, 0, 44)
        gradient.setColorAt(0, QColor('#ffdc99')); gradient.setColorAt(.45, QColor('#ff9f58')); gradient.setColorAt(1, QColor('#d95134'))
        painter.setPen(QPen(QColor('#ffbf7c'), .6)); painter.setBrush(gradient); painter.drawPath(flame)
        # A narrow light pass across the mark, clipped to its silhouette.
        painter.setClipPath(flame)
        sweep = -80+self.phase*180
        light = QLinearGradient(0, sweep-18, 0, sweep+18)
        light.setColorAt(0, QColor(255, 255, 255, 0)); light.setColorAt(.5, QColor(255, 241, 212, 100)); light.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(-45, -60, 90, 120), light)
        painter.restore()
        painter.setOpacity(min(1.0, max(0.0, (self.phase-.08)*4)))
        font = QFont('Segoe UI', 27, QFont.DemiBold); font.setLetterSpacing(QFont.AbsoluteSpacing, 4)
        painter.setFont(font); painter.setPen(QColor('#eef2f7'))
        painter.drawText(QRectF(0, 174, 560, 48), Qt.AlignCenter, 'FIREBLADE')
        font = QFont('Segoe UI', 9); font.setLetterSpacing(QFont.AbsoluteSpacing, 2)
        painter.setFont(font); painter.setPen(QColor('#93a1b4'))
        painter.drawText(QRectF(0, 226, 560, 25), Qt.AlignCenter, 'INVESTIGATION NUMÉRIQUE')
        painter.setOpacity(1)
        painter.setPen(QPen(QColor('#263241'), 1)); painter.drawLine(192, 274, 368, 274)
        painter.setPen(Qt.NoPen); painter.setBrush(QColor('#ed965b'))
        painter.drawRoundedRect(QRectF(192, 273, 176*self.phase, 2), 1, 1)
        painter.setFont(QFont('Segoe UI', 8)); painter.setPen(QColor('#6e7c8f'))
        painter.drawText(QRectF(0, 286, 560, 22), Qt.AlignCenter, __version__)
