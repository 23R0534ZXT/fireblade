"""Small vector startup animation; no network, asset extraction or worker sleep."""
import math

from PySide6.QtCore import QEasingCurve, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class StartupAnimation(QWidget):
    finished = Signal()

    def __init__(self):
        super().__init__(None, Qt.SplashScreen | Qt.FramelessWindowHint)
        self.setFixedSize(560, 300)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.phase = 0.0
        self.animation = QVariantAnimation(self)
        self.animation.setStartValue(0.0); self.animation.setEndValue(1.0)
        self.animation.setDuration(2400)
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
        background = QLinearGradient(0, 0, self.width(), self.height())
        background.setColorAt(0, QColor('#101b2d')); background.setColorAt(1, QColor('#080d17'))
        painter.fillRect(self.rect(), background)
        painter.setPen(QPen(QColor('#263854'), 1))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -2, -2), 16, 16)
        painter.save()
        painter.translate(280, 94)
        painter.scale(.8+.2*self.phase, .8+.2*self.phase)
        flame = QPainterPath()
        flame.moveTo(0, -49); flame.cubicTo(9, -12, 46, -6, 30, 26)
        flame.cubicTo(14, 53, -33, 41, -32, 12)
        flame.cubicTo(-32, -6, -12, -16, -14, -30)
        flame.cubicTo(-8, -21, -4, -10, -4, -2)
        flame.cubicTo(9, -18, -5, -28, 0, -49)
        gradient = QLinearGradient(0, -40, 0, 44)
        gradient.setColorAt(0, QColor('#ffce72')); gradient.setColorAt(1, QColor('#ef533b'))
        painter.setPen(Qt.NoPen); painter.setBrush(gradient); painter.drawPath(flame)
        painter.restore()
        painter.setPen(QColor('#f2f6ff')); painter.setFont(QFont('Segoe UI', 28, QFont.Bold))
        painter.drawText(0, 155, 560, 50, Qt.AlignCenter, 'FIREBLADE')
        painter.setFont(QFont('Segoe UI', 10)); painter.setPen(QColor('#a6b8d3'))
        stage = ('Préparation de votre espace…' if self.phase < .4 else
                 'Fichiers · dossiers · disques' if self.phase < .8 else 'Prêt à enquêter')
        painter.drawText(0, 207, 560, 28, Qt.AlignCenter, stage)
        painter.setPen(Qt.NoPen); painter.setBrush(QColor('#243047'))
        painter.drawRoundedRect(180, 260, 200, 3, 1.5, 1.5)
        painter.setBrush(QColor('#ff9c5b'))
        painter.drawRoundedRect(180, 260, max(3, int(200*self.phase)), 3, 1.5, 1.5)
        for i in range(7):
            x = 220+i*19+math.sin(i+self.phase*3)*5
            y = 109-(self.phase*60+i*17)%83
            painter.setBrush(QColor(255, 157, 83, int(100*self.phase)))
            painter.drawEllipse(int(x), int(y), 2, 2)
