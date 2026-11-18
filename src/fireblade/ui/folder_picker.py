"""A directory picker with real Ctrl/Shift selection on every supported platform."""
import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QFileDialog,
    QHBoxLayout, QLabel, QListWidget, QPushButton, QVBoxLayout)


class FolderPicker(QFileDialog):
    def __init__(self, parent=None):
        super().__init__(parent, 'Dossiers à parser')
        self.setOption(QFileDialog.DontUseNativeDialog, True)
        self.setFileMode(QFileDialog.Directory)
        self.setOption(QFileDialog.ShowDirsOnly, True)
        self.setViewMode(QFileDialog.Detail)
        self.setLabelText(QFileDialog.Accept, 'Sélectionner')
        self.setLabelText(QFileDialog.FileName, 'Dossiers :')
        for view in self.findChildren(QAbstractItemView):
            if view.objectName() in ('listView', 'treeView'):
                view.setSelectionMode(QAbstractItemView.ExtendedSelection)


def source_key(path):
    """How two selections are told apart: Windows compares paths case-insensitively."""
    return os.path.normcase(os.path.abspath(str(path)))


class SourcesDialog(QDialog):
    """Files and folders in one selection, because a triage export is rarely one or the other.

    The old gesture only accepted folders, so a handful of EVTX files copied to the
    desktop meant one import per file. This dialog keeps the examiner's list in front
    of them, and the collection below reads it as one operation: one report, one
    journal, and duplicates found across every source in the list.
    """

    def __init__(self, parent=None, start=None):
        super().__init__(parent)
        self.setWindowTitle('Import evidence')
        self.resize(680, 420)
        self._start = str(start) if start else ''
        layout = QVBoxLayout(self)
        intro = QLabel('Files and folders read in one operation. Each of them gets a row in the '
                       'report, with its reason when it was not read.')
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.list, 1)
        controls = QHBoxLayout()
        self.add_files = QPushButton('Add files…')
        self.add_files.clicked.connect(self.choose_files)
        self.add_folder = QPushButton('Add folder…')
        self.add_folder.clicked.connect(self.choose_folder)
        self.remove = QPushButton('Remove')
        self.remove.clicked.connect(self.remove_selected)
        for button in (self.add_files, self.add_folder, self.remove):
            controls.addWidget(button)
        controls.addStretch()
        layout.addLayout(controls)
        self.count = QLabel()
        layout.addWidget(self.count)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText('Import')
        self.buttons.button(QDialogButtonBox.Cancel).setText('Cancel')
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.entries = []
        self.refresh()

    def add_paths(self, paths):
        """Append what was chosen, once each, keeping the examiner's order."""
        known = {source_key(path) for path in self.entries}
        for path in paths:
            path = str(path)
            if not path or source_key(path) in known:
                continue
            self.entries.append(path)
            known.add(source_key(path))
            self.list.addItem(path)
        self.refresh()
        return self.entries

    def choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, 'Files to import', self._start)
        if paths:
            self._start = str(Path(paths[0]).parent)
            self.add_paths(paths)

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, 'Folder to import', self._start)
        if path:
            self._start = path
            self.add_paths([path])

    def remove_selected(self):
        rows = sorted({self.list.row(item) for item in self.list.selectedItems()}, reverse=True)
        for row in rows:
            self.list.takeItem(row)
            del self.entries[row]
        self.refresh()

    def refresh(self):
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(bool(self.entries))
        folders = sum(1 for path in self.entries if Path(path).is_dir())
        files = len(self.entries) - folders
        self.count.setText(f'{files} file(s) · {folders} folder(s)')
        self.remove.setEnabled(bool(self.entries))

    def sources(self):
        return list(self.entries)


def choose_import_sources(parent, start=None):
    dialog = SourcesDialog(parent, start)
    try:
        return dialog.sources() if dialog.exec() == QDialog.Accepted else []
    finally:
        dialog.deleteLater()
