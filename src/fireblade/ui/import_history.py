"""What an import did, file by file, and a way to try again differently.

An import of a folder of evidence is a list of decisions: this file was read, this one was
recognised as a copy, this one had no reader, this one failed and why. Without that list,
"many EVTX were not imported" has no answer — the report table is dense, and the reason for
one file is two clicks away.

The dialog shows the whole list, filters it (all, imported, not imported, duplicates), lets
the analyst tick the files worth another attempt, and hands them to the same reader choice
the Imports panel already offers.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox,
                               QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget,
                               QTableWidgetItem, QTextBrowser, QVBoxLayout)

from fireblade.core.i18n import translate

IMPORTED = ('complete', 'complete_with_warnings', 'attention')
NOT_IMPORTED = ('unsupported', 'error', 'skipped', 'no_output', 'cancelled')


def outcome(entry):
    """One word for the row, so the filter can be honest about what counts as imported."""
    status = str(entry.get('status') or '')
    if status == 'duplicate':
        return 'duplicate'
    if status in IMPORTED:
        return 'imported'
    if status in NOT_IMPORTED:
        return 'not_imported'
    return 'other'


def rows_of(report):
    return list((report or {}).get('files') or [])


def summarise(rows):
    counts = {'imported': 0, 'duplicate': 0, 'not_imported': 0, 'other': 0}
    for entry in rows:
        counts[outcome(entry)] += 1
    return counts


class ImportHistoryDialog(QDialog):
    def __init__(self, report, on_retry=None, parent=None):
        super().__init__(parent)
        self.report = report
        self.on_retry = on_retry
        self.entries = rows_of(report)
        self.visible = list(self.entries)
        self.setWindowTitle(translate('Historique de l’import'))
        self.resize(1000, 640)
        layout = QVBoxLayout(self)

        counts = summarise(self.entries)
        self.summary = QLabel(translate('{} fichier(s) · {} importé(s) · {} doublon(s) · {} non importé(s)').format(
            len(self.entries), counts['imported'], counts['duplicate'], counts['not_imported']))
        layout.addWidget(self.summary)

        tools = QHBoxLayout()
        self.filter = QComboBox()
        for label, value in ((translate('Tout'), 'all'), (translate('Importés'), 'imported'),
                             (translate('Non importés'), 'not_imported'),
                             (translate('Doublons'), 'duplicate')):
            self.filter.addItem(label, value)
        self.filter.currentIndexChanged.connect(self.apply_filter)
        tools.addWidget(self.filter)
        tick_all = QPushButton(translate('Tout cocher'))
        tick_all.clicked.connect(lambda: self.tick(True))
        tick_none = QPushButton(translate('Rien cocher'))
        tick_none.clicked.connect(lambda: self.tick(False))
        tools.addWidget(tick_all)
        tools.addWidget(tick_none)
        tools.addStretch()
        layout.addLayout(tools)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([translate('Fichier'), translate('État'),
                                              translate('Lecteur'), translate('Raison')])
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self.show_selected)
        self.table.itemChanged.connect(lambda _item: self.update_buttons())
        layout.addWidget(self.table, 3)

        self.details = QTextBrowser()
        self.details.setPlaceholderText(translate('Sélectionnez un fichier pour lire pourquoi il a été '
                                                  'importé, écarté, ou refusé.'))
        layout.addWidget(self.details, 1)

        buttons = QHBoxLayout()
        self.retry_button = QPushButton(translate('Réessayer la sélection avec un autre lecteur…'))
        self.retry_button.clicked.connect(self.retry)
        buttons.addWidget(self.retry_button)
        buttons.addStretch()
        layout.addLayout(buttons)

        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.button(QDialogButtonBox.Close).setText(translate('Fermer'))
        close.rejected.connect(self.reject)
        layout.addWidget(close)

        self.apply_filter()

    # -- list ------------------------------------------------------------------------
    def apply_filter(self):
        wanted = self.filter.currentData() if hasattr(self, 'filter') else 'all'
        self.visible = [entry for entry in self.entries if wanted in ('all', outcome(entry))]
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.visible))
        for index, entry in enumerate(self.visible):
            name = QTableWidgetItem(Path(str(entry.get('path', ''))).name or str(entry.get('path', '')))
            name.setData(Qt.UserRole, str(entry.get('path', '')))
            name.setFlags(name.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            name.setCheckState(Qt.Unchecked)
            name.setToolTip(str(entry.get('path', '')))
            state = QTableWidgetItem({
                'imported': translate('importé'), 'duplicate': translate('doublon'),
                'not_imported': translate('non importé')}.get(outcome(entry), translate('autre')))
            if outcome(entry) == 'not_imported':
                state.setForeground(Qt.red)
            readers = ', '.join(sorted({run.get('tool', '') for run in entry.get('runs', []) if run.get('tool')})) or '—'
            self.table.setItem(index, 0, name)
            self.table.setItem(index, 1, state)
            self.table.setItem(index, 2, QTableWidgetItem(readers))
            self.table.setItem(index, 3, QTableWidgetItem(str(entry.get('reason') or entry.get('error') or '')))
        self.table.blockSignals(False)
        self.update_buttons()

    def tick(self, checked):
        self.table.blockSignals(True)
        for index in range(self.table.rowCount()):
            self.table.item(index, 0).setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.table.blockSignals(False)
        self.update_buttons()

    def checked_paths(self):
        paths = []
        for index in range(self.table.rowCount()):
            item = self.table.item(index, 0)
            if item is not None and item.checkState() == Qt.Checked:
                paths.append(str(item.data(Qt.UserRole)))
        return paths

    def current_entry(self):
        index = self.table.currentRow()
        return self.visible[index] if 0 <= index < len(self.visible) else None

    def show_selected(self):
        entry = self.current_entry()
        if entry is None:
            self.details.clear()
            return
        lines = [str(entry.get('path', '')), '',
                 translate('État : ')+str(entry.get('status', '')),
                 translate('Raison : ')+(str(entry.get('reason') or entry.get('error') or translate('aucune')))]
        if entry.get('duplicate_of'):
            lines.append(translate('Contenu identique à : ')+str(entry['duplicate_of']))
        if entry.get('similar_to'):
            lines.append(translate('Ressemblant à {} (même nom, même taille, contenu différent : importé)').format(
                entry['similar_to']))
        if entry.get('sha256'):
            lines.append('SHA-256 : '+str(entry['sha256']))
        for run in entry.get('runs', []):
            outputs = ', '.join(Path(str(out.get('csv', ''))).name for out in run.get('outputs', []))
            lines.append(translate('Lecteur {} · {} · {}').format(run.get('tool', ''),
                                                                   run.get('status', ''),
                                                                   outputs or translate('aucune sortie')))
            if run.get('error'):
                lines.append('   '+str(run['error'])[:800])
        self.details.setPlainText('\n'.join(lines))

    def update_buttons(self):
        self.retry_button.setEnabled(bool(self.checked_paths()) and callable(self.on_retry))

    # -- action ----------------------------------------------------------------------
    def retry(self):
        paths = self.checked_paths()
        if not paths or not callable(self.on_retry):
            return
        from fireblade.ui.collection_report import ReaderDialog
        dialog = ReaderDialog(paths[0], self)
        accepted = dialog.exec()
        reader = dialog.reader()
        dialog.deleteLater()
        if accepted != QDialog.DialogCode.Accepted:
            return
        self.accept()
        self.on_retry(paths, reader)
