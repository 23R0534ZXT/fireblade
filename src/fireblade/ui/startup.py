"""Lightweight vector ident; animation remains optional and event driven."""
import math

from PySide6.QtCore import QEasingCurve, QElapsedTimer, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget
from fireblade import __version__


class StartupAnimation(QWidget):
    finished = Signal()

    def __init__(self):
        super().__init__(None, Qt.SplashScreen | Qt.FramelessWindowHint)
        self.setWindowTitle('Fireblade')
        self.setFixedSize(560, 360)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.phase = 0.0
        self.clock = QElapsedTimer(); self.clock.start()
        self.last_frame = -100
        self.animation = QVariantAnimation(self)
        self.animation.setStartValue(0.0); self.animation.setEndValue(1.0)
        self.animation.setDuration(10000)
        self.animation.setEasingCurve(QEasingCurve.Linear)
        self.animation.valueChanged.connect(self.advance)
        self.animation.finished.connect(self.finished.emit)
        screen = self.screen().availableGeometry()
        self.move(screen.center()-self.rect().center())

    def advance(self, value):
        self.phase = value
        now = self.clock.elapsed()
        if now-self.last_frame >= 33 or value == 1.0:
            self.last_frame = now
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
        # Embers ignite into a layered fire, then give way to the brand mark.
        scene_opacity = max(0.0, min(1.0, (0.9-self.phase)/.14))
        heat = min(1.0, max(0.0, (self.phase-.06)/.4))
        seconds = self.phase*10
        painter.save(); painter.setOpacity(scene_opacity)
        hearth = QRadialGradient(280, 175, 115)
        hearth.setColorAt(0, QColor(255, 94, 25, int(70*heat)))
        hearth.setColorAt(1, QColor(11, 16, 24, 0))
        painter.fillRect(QRectF(140, 40, 280, 185), hearth)
        painter.setPen(QPen(QColor('#28303a'), 1))
        painter.drawLine(155, 190, 405, 190)
        # Charred wood, cut ends and warm cracks.
        for angle in (-17, 17):
            painter.save(); painter.translate(280, 178); painter.rotate(angle)
            painter.setBrush(QColor('#241d1a')); painter.setPen(QPen(QColor('#4d3428'), 1))
            painter.drawRoundedRect(QRectF(-48, -6, 96, 13), 6, 6)
            painter.setPen(QPen(QColor(216, 92, 34, int(80+100*heat)), 1))
            for x in (-32, -12, 14, 31):painter.drawLine(x, -3, x+8, 3)
            painter.setPen(QPen(QColor('#6d4731'), 1)); painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QRectF(38, -4, 8, 9)); painter.restore()
        for i in range(11):
            flicker = .6+.4*math.sin(seconds*4+i*2)
            painter.setPen(Qt.NoPen); painter.setBrush(QColor(255, 115, 39, int((55+170*heat)*flicker)))
            painter.drawEllipse(QRectF(249+i*6, 175+math.sin(i*2)*4, 3, 2))
        # Independent tongues keep the motion organic without particle simulation.
        for i, x in enumerate((-24, 22, -10, 10, 0)):
            height = (51+i*12)*heat*(.92+.08*math.sin(seconds*5+i*1.9))
            width = (17 if i<4 else 23)*max(.15, heat)
            sway = math.sin(seconds*3+i*2)*8*heat
            path = QPainterPath(); path.moveTo(280+x-width, 174)
            path.cubicTo(280+x-width*1.8, 153, 280+x+sway-8, 174-height*.65, 280+x+sway, 174-height)
            path.cubicTo(280+x+sway+2, 174-height*.5, 280+x+width*1.6, 151, 280+x+width, 174)
            path.closeSubpath()
            fire = QLinearGradient(0, 174-height, 0, 180)
            fire.setColorAt(0, QColor('#ffcb67')); fire.setColorAt(.4, QColor('#ff8b36')); fire.setColorAt(1, QColor('#d94c27'))
            painter.setPen(Qt.NoPen); painter.setBrush(fire); painter.drawPath(path)
            if i==4:
                painter.save(); painter.translate(280+x, 174); painter.scale(.42, .62); painter.translate(-280-x, -174)
                painter.setBrush(QColor('#ffe4a0')); painter.drawPath(path); painter.restore()
        for i in range(9):
            age = (seconds*.35+i*.137)%1
            if heat<=.12:continue
            x = 280+math.sin(i*7+seconds)*18+math.sin(age*6+i)*12
            y = 170-age*125
            painter.setBrush(QColor(255, 181, 92, int(heat*(1-age)*180)))
            painter.drawEllipse(QRectF(x, y, 1.5, 3))
        # Smoke is restrained and fades as it rises.
        for i in range(3):
            age = (seconds*.15+i/3)%1
            smoke = QPainterPath(); smoke.moveTo(277+i*3, 160-age*80)
            smoke.cubicTo(250, 140-age*80, 309, 121-age*80, 284, 104-age*80)
            painter.setBrush(Qt.NoBrush); painter.setPen(QPen(QColor(156, 162, 173, int(heat*(1-age)*24)), 2))
            painter.drawPath(smoke)
        painter.restore()
        reveal = min(1.0, max(0.0, (self.phase-.78)/.18))
        reveal = 1-(1-reveal)**3
        painter.save()
        painter.translate(280, 120+8*(1-reveal))
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
        painter.setOpacity(min(1.0, max(0.0, (self.phase-.02)*4)))
        font = QFont('Segoe UI', 27, QFont.DemiBold); font.setLetterSpacing(QFont.AbsoluteSpacing, 4)
        painter.setFont(font); painter.setPen(QColor('#eef2f7'))
        painter.drawText(QRectF(0, 220, 560, 48), Qt.AlignCenter, 'FIREBLADE')
        font = QFont('Segoe UI', 9); font.setLetterSpacing(QFont.AbsoluteSpacing, 2)
        painter.setFont(font); painter.setPen(QColor('#93a1b4'))
        painter.drawText(QRectF(0, 271, 560, 25), Qt.AlignCenter, 'INVESTIGATION NUMÉRIQUE')
        painter.setOpacity(1)
        painter.setPen(QPen(QColor('#263241'), 1)); painter.drawLine(192, 316, 368, 316)
        painter.setPen(Qt.NoPen); painter.setBrush(QColor('#ed965b'))
        painter.drawRoundedRect(QRectF(192, 315, 176*self.phase, 2), 1, 1)
        painter.setFont(QFont('Segoe UI', 8)); painter.setPen(QColor('#6e7c8f'))
        painter.drawText(QRectF(0, 330, 560, 22), Qt.AlignCenter, __version__)
