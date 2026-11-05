"""Column manager: visibility, order, width and pinning in one window.

The grid already remembers order and widths per artifact format; this dialog is
the readable way to change them without hunting for a header to drag.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox,
                               QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QPushButton, QSpinBox, QVBoxLayout)

PINS = [("Aucun", "none"), ("Figée à gauche", "left"), ("Figée à droite", "right")]


class ColumnManager(QDialog):
    """Two panes: available columns, and displayed columns in display order."""

    def __init__(self, headers, state, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Colonnes")
        self.resize(720, 480)
        self.headers = list(headers)
        order = list(state.get("order") or range(len(self.headers)))
        hidden = set(state.get("hidden") or ())
        self.pins = {}
        for column in state.get("left") or ():
            self.pins[column] = "left"
        for column in state.get("right") or ():
            self.pins[column] = "right"
        self.widths = dict(state.get("widths") or {})
        self.showing = [c for c in order if c not in hidden and 0 <= c < len(self.headers)]
        self.available = [c for c in range(len(self.headers)) if c not in self.showing]

        body = QHBoxLayout()
        self.left = QListWidget()
        self.left.setSelectionMode(QAbstractItemView.SingleSelection)
        self.right = QListWidget()
        self.right.setDragDropMode(QAbstractItemView.InternalMove)
        self.right.setSelectionMode(QAbstractItemView.SingleSelection)
        self.left.itemDoubleClicked.connect(lambda item: self.show_column(item.data(Qt.UserRole)))
        self.right.itemDoubleClicked.connect(lambda item: self.hide_column(item.data(Qt.UserRole)))
        self.right.currentItemChanged.connect(lambda *_args: self.sync_controls())

        middle = QVBoxLayout()
        self.add_button = QPushButton("Ajouter →")
        self.remove_button = QPushButton("← Retirer")
        self.add_button.clicked.connect(self.add_selected)
        self.remove_button.clicked.connect(self.remove_selected)
        middle.addStretch()
        middle.addWidget(self.add_button)
        middle.addWidget(self.remove_button)
        middle.addStretch()

        left_box = QVBoxLayout()
        left_box.addWidget(QLabel("Non affichées"))
        left_box.addWidget(self.left)
        right_box = QVBoxLayout()
        right_box.addWidget(QLabel("Affichées · glissez pour réordonner"))
        right_box.addWidget(self.right)
        body.addLayout(left_box, 1)
        body.addLayout(middle)
        body.addLayout(right_box, 1)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Largeur"))
        self.width = QSpinBox()
        self.width.setRange(24, 2000)
        self.width.setSuffix(" px")
        self.width.valueChanged.connect(self.apply_controls)
        controls.addWidget(self.width)
        controls.addSpacing(12)
        controls.addWidget(QLabel("Épinglage"))
        self.pin = QComboBox()
        for label, code in PINS:
            self.pin.addItem(label, code)
        self.pin.currentIndexChanged.connect(self.apply_controls)
        controls.addWidget(self.pin)
        controls.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        hint = QLabel("L'ordre et les largeurs sont mémorisés pour ce format d'artefact.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addLayout(body, 1)
        layout.addLayout(controls)
        layout.addWidget(buttons)
        self.refresh()

    # ---- model -------------------------------------------------------
    def refresh(self):
        current_left = self._selected(self.left)
        current_right = self._selected(self.right)
        self.left.blockSignals(True)
        self.right.blockSignals(True)
        self.left.clear()
        self.right.clear()
        for column in self.available:
            self.left.addItem(self._item(column))
        for column in self.showing:
            self.right.addItem(self._item(column))
        self.left.blockSignals(False)
        self.right.blockSignals(False)
        self._select(self.left, current_left)
        self._select(self.right, current_right if current_right is not None else (self.showing[0] if self.showing else None))
        self.sync_controls()

    def _item(self, column):
        item = QListWidgetItem(self.headers[column])
        item.setData(Qt.UserRole, column)
        return item

    @staticmethod
    def _selected(listing):
        item = listing.currentItem()
        return item.data(Qt.UserRole) if item is not None else None

    @staticmethod
    def _select(listing, column):
        if column is None:
            return
        for row in range(listing.count()):
            if listing.item(row).data(Qt.UserRole) == column:
                listing.setCurrentRow(row)
                return

    def show_column(self, column, position=None):
        if column in self.showing or column not in range(len(self.headers)):
            return
        if column not in self.showing:
            self.available = [c for c in self.available if c != column]
            if position is None or not 0 <= position <= len(self.showing):
                self.showing.append(column)
            else:
                self.showing.insert(position, column)
        self.refresh()
        self._select(self.right, column)

    def hide_column(self, column):
        if column not in self.showing:
            return
        index = self.showing.index(column)
        self.showing.remove(column)
        # Keep the original ordering inside the hidden pane.
        self.available = sorted(set(self.available) | {column})
        self.refresh()
        self._select(self.right, self.showing[min(index, len(self.showing) - 1)] if self.showing else None)

    def set_width(self, column, pixels):
        self.widths[column] = max(24, int(pixels))

    def set_pin(self, column, pin):
        if pin not in ("none", "left", "right"):
            raise ValueError("Épinglage inconnu")
        self.pins[column] = pin

    def state(self) -> dict:
        """Display order is the right pane, read top to bottom."""
        self.sync_order()
        left = [c for c in self.showing if self.pins.get(c) == "left"]
        right = [c for c in self.showing if self.pins.get(c) == "right"]
        return dict(order=list(self.showing) + list(self.available),
                    hidden=list(self.available),
                    left=left, right=right,
                    widths={c: w for c, w in self.widths.items() if c in self.showing})

    # ---- widgets -----------------------------------------------------
    def sync_order(self):
        """The pane order is the truth; drag and drop reorders widgets, not the list."""
        if self.right.count() != len(self.showing):
            return
        self.showing = [self.right.item(row).data(Qt.UserRole) for row in range(self.right.count())]

    def add_selected(self):
        column = self._selected(self.left)
        if column is not None:
            self.show_column(column)

    def remove_selected(self):
        column = self._selected(self.right)
        if column is not None:
            self.hide_column(column)

    def sync_controls(self):
        column = self._selected(self.right)
        enabled = column is not None
        self.width.setEnabled(enabled)
        self.pin.setEnabled(enabled)
        if not enabled:
            return
        previous = (self.width.blockSignals(True), self.pin.blockSignals(True))
        self.width.setValue(self.widths.get(column, 120))
        self.pin.setCurrentIndex(max(0, self.pin.findData(self.pins.get(column, "none"))))
        self.width.blockSignals(previous[0])
        self.pin.blockSignals(previous[1])

    def apply_controls(self):
        column = self._selected(self.right)
        if column is None:
            return
        self.set_width(column, self.width.value())
        self.set_pin(column, self.pin.currentData())
