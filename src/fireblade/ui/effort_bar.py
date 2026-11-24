"""The effort control: one slider, and a bar that says what it costs the machine.

Nothing here is a number the analyst has to guess. The levels are computed from the
machine Fireblade is running on, and the colour answers the only question that matters
while a collection runs: is the desktop still mine?
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSlider, QWidget

from fireblade.core.machine import LEVELS, describe, effort

COLOURS = {"green": "#2f9e58", "amber": "#cf8a1c", "red": "#c0392b"}
WIDTH = 64


class EffortBar(QWidget):
    """Four steps from 'leave my machine alone' to 'use all of it'."""

    chosen = Signal(str)

    def __init__(self, level="balanced", parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self.label = QLabel("Effort")
        row.addWidget(self.label)
        self.slider = QSlider(Qt.Horizontal, self)
        self.slider.setRange(0, len(LEVELS) - 1)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(1)
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.setFixedWidth(110)
        self.slider.setToolTip(
            "Light keeps the machine responsive; Maximum gives the import everything it can take."
        )
        row.addWidget(self.slider)
        self.bar = QFrame(self)
        self.bar.setFixedHeight(6)
        row.addWidget(self.bar)
        self.text = QLabel(self)
        row.addWidget(self.text)
        row.addStretch()
        self.slider.valueChanged.connect(self._moved)
        self.set_level(level, notify=False)

    def _moved(self, index):
        self.set_level(LEVELS[index], notify=True)

    def set_level(self, level, notify=False):
        if level not in LEVELS:
            level = "balanced"
        self.level = level
        item = effort(level)
        self.slider.blockSignals(True)
        self.slider.setValue(LEVELS.index(level))
        self.slider.blockSignals(False)
        # The bar grows with what is taken and turns red once the machine will feel it.
        self.bar.setFixedWidth(max(6, int(round(item.share * WIDTH))))
        self.bar.setStyleSheet("background:%s;border-radius:3px;" % COLOURS[item.tone])
        self.text.setText("%s · %s" % (level.capitalize(), describe(item)))
        self.text.setToolTip(
            "This machine: %s. The import grows its budget on its own if a "
            "file needs more than this." % describe(item)
        )
        if notify:
            self.chosen.emit(level)
