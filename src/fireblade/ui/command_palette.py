"""Keyboard command palette: every menu command, filtered as you type."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QLineEdit, QListWidget,
                               QListWidgetItem, QVBoxLayout)


def flatten_actions(menubar):
    """Every leaf action of the menu bar, prefixed with its submenu path."""
    entries, seen = [], set()

    def walk(menu, prefix):
        for action in menu.actions():
            if action.isSeparator():
                continue
            label = action.text().replace("&", "").strip()
            if action.menu() is not None:
                if label:
                    walk(action.menu(), f"{prefix}{label} › ")
                else:
                    walk(action.menu(), prefix)
                continue
            if not label or action in seen:
                continue
            seen.add(action)
            entries.append((f"{prefix}{label}", action))

    for action in menubar.actions():
        if action.menu() is not None:
            walk(action.menu(), "")
    return entries


class CommandPalette(QDialog):
    """Ctrl+K: type a command, press Enter. Unknown buttons stop being hidden."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Commandes")
        self.resize(560, 380)
        self.entries = flatten_actions(parent.menuBar())
        self.input = QLineEdit(self)
        self.input.setPlaceholderText("Tapez une commande…")
        self.listing = QListWidget(self)
        self.listing.setSelectionMode(QAbstractItemView.SingleSelection)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self.input)
        layout.addWidget(self.listing)
        self.input.textChanged.connect(self.filter)
        self.input.returnPressed.connect(self.run_current)
        self.listing.itemActivated.connect(lambda _item: self.run_current())
        self.filter("")

    def filter(self, text):
        needle = text.strip().casefold()
        self.listing.clear()
        for label, action in self.entries:
            if needle and needle not in label.casefold():
                continue
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, action)
            if not action.isEnabled():
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.listing.addItem(item)
        if self.listing.count():
            self.listing.setCurrentRow(0)

    def run_current(self):
        item = self.listing.currentItem()
        if item is None or not (item.flags() & Qt.ItemIsEnabled):
            return
        action = item.data(Qt.UserRole)
        self.accept()
        if action is not None and hasattr(action, "trigger"):
            action.trigger()
