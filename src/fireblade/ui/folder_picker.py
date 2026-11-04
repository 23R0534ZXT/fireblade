"""A directory picker with real Ctrl/Shift selection on every supported platform."""
from PySide6.QtWidgets import QAbstractItemView, QDialog, QFileDialog


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


def choose_collection_directories(parent):
    dialog = FolderPicker(parent)
    try:
        return dialog.selectedFiles() if dialog.exec() == QDialog.Accepted else []
    finally:
        dialog.deleteLater()
