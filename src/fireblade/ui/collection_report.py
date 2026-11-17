"""Filterable collection outcome table, with actions on what could not be read."""
from collections import Counter
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QRadioButton, QSplitter, QTableView,
    QTextBrowser, QVBoxLayout, QWidget)

from fireblade.core import report_actions as actions
from fireblade.core.i18n import translate
from fireblade.ui.flow_layout import FlowLayout

STATUSES = {'pending':'En attente', 'running':'En cours', 'complete':'Terminé',
    'complete_with_warnings':'Terminé avec avertissements', 'unsupported':'Non reconnu',
    'skipped':'Ignoré', 'error':'Erreur', 'cancelled':'Interrompu', 'attention':'À vérifier',
    'no_output':'Aucune sortie', 'companion':'Journal de transaction', 'deleted':'Supprimé'}

PREVIEW_LIMIT = 64 * 1024


def outcome(entry):
    state=entry['status']
    # An entry parked by the examiner keeps its state, but leaves the working counts.
    if entry.get('ignored'):return 'ignored'
    # A file can be "attention" because one of several readers failed.
    # Keep that failure discoverable in the error filter and counters.
    if state in ('error','cancelled') or any(run['status'] in ('error','cancelled') for run in entry.get('runs',[])):return 'errors'
    if state in ('complete_with_warnings','attention','no_output'):return 'warnings'
    if state in ('unsupported','skipped','deleted'):return 'unsupported'
    return 'complete' if state=='complete' else 'other'


def preview_text(path, limit=PREVIEW_LIMIT):
    """Readable preview of any file: text when it decodes, bytes otherwise.

    The point is to recognise a file without opening another tool, so the preview
    must never fail: an unreadable file comes back as a message, and a binary file
    is shown as bytes rather than as mojibake.
    """
    path=Path(path)
    try:
        with path.open('rb') as stream:data=stream.read(limit)
        size=path.stat().st_size
    except OSError as error:return translate('Fichier illisible : ')+str(error)
    if not data:return translate('Fichier vide (0 octet).')
    controls=sum(1 for byte in data if byte<9 or 13<byte<32)
    try:
        text=data.decode('utf-8')
    except UnicodeDecodeError:
        if b'\0' in data or controls>max(8,len(data)//20):
            rows=[]
            for offset in range(0,len(data),16):
                block=data[offset:offset+16]
                printable=''.join(chr(b) if 32<=b<127 else '.' for b in block)
                rows.append(f'{offset:08x}  '+' '.join(f'{b:02x}' for b in block).ljust(47)+'  '+printable)
            text='\n'.join(rows)
        else:text=data.decode('cp1252','replace')
    if size>len(data):text+='\n\n'+translate('Aperçu tronqué : {} premiers octets sur {}.').format(len(data),size)
    return text


class ReaderDialog(QDialog):
    """Choose how to read a file the collection could not identify."""

    READERS = (('text', 'Texte', 'Une ligne par ligne ; un horodatage est gardé seulement s\'il ouvre la ligne.'),
               ('html', 'Page HTML enregistrée', 'Texte visible et liens, sans navigateur ni dépendance.'),
               ('pdf', 'PDF (couche texte)', 'Le texte du document, page par page ; un scan reste non lu.'),
               ('csv', 'Tableau CSV / TSV', 'Colonnes importées telles quelles, sans réinterprétation.'))

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(translate('Relancer avec un lecteur'))
        self.resize(580, 330)
        layout = QVBoxLayout(self)
        name = QLabel(str(path))
        name.setWordWrap(True)
        layout.addWidget(name)
        from fireblade.core import pdfreader
        self._choices = []
        for code, label, hint in self.READERS:
            choice = QRadioButton(translate(label))
            choice.setProperty('reader', code)
            layout.addWidget(choice)
            self._choices.append(choice)
            reason = QLabel(translate(hint))
            reason.setWordWrap(True)
            reason.setIndent(24)
            layout.addWidget(reason)
            if code == 'pdf' and not pdfreader.available():
                # Never offer a reader that cannot read: say what is missing instead.
                choice.setEnabled(False)
                reason.setText(translate("Extension pypdf absente : installez-la pour lire un PDF."))
        self._choices[0].setChecked(True)
        note = QLabel(translate("Le fichier est lu, jamais modifié. Son empreinte SHA-256 est relevée, et une "
                                "lecture ultérieure sera refusée si le fichier change."))
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(translate('Analyser'))
        buttons.button(QDialogButtonBox.Cancel).setText(translate('Annuler'))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def reader(self):
        for choice in self._choices:
            if choice.isChecked():
                return choice.property('reader')
        return 'text'


class OutcomeModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent);self.entries=[]

    def rowCount(self, parent=QModelIndex()):return 0 if parent.isValid() else len(self.entries)
    def columnCount(self, parent=QModelIndex()):return 5

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation==Qt.Horizontal and role==Qt.DisplayRole:
            return translate(['État','Fichier','Lecteurs','Motif','Sorties'][section])

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():return None
        entry=self.entries[index.row()]
        if role==Qt.ToolTipRole:return str(entry.get('path',''))
        if role==Qt.DisplayRole:
            status=translate(STATUSES.get(entry['status'],entry['status']))
            if outcome(entry)=='errors' and entry['status']=='attention':status+=translate(' · erreur de lecteur')
            if entry.get('ignored'):status+=translate(' · écarté')
            return [status,str(entry.get('path','')),
                    ', '.join(entry.get('tools',[])),
                    translate(str(entry.get('error') or entry.get('reason') or '')),
                    sum(len(run.get('outputs',[])) for run in entry.get('runs',[]))][index.column()]


class OutcomeFilter(QSortFilterProxyModel):
    status='';query=''

    def filterAcceptsRow(self, row, parent):
        entry=self.sourceModel().entries[row]
        if self.status and outcome(entry)!=self.status:return False
        return self.query in (str(entry.get('path',''))+' '+str(entry.get('error',''))+' '+
                              ' '.join(entry.get('tools',[]))).casefold()


class CollectionReport(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._text='';self.report=None;self.on_changed=None;self.on_analyse=None
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        self.summary=QLabel();self.summary.setTextFormat(Qt.PlainText);self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        row=QHBoxLayout()
        self.status=QComboBox()
        for label,value in [('Tous les fichiers',''),('Réussis','complete'),('Avertissements / à vérifier','warnings'),
                            ('Erreurs / interrompus','errors'),('Non reconnus / ignorés','unsupported'),
                            ('Écartés du bilan','ignored')]:
            self.status.addItem(label,value)
        self.search=QLineEdit();self.search.setPlaceholderText('Chercher un fichier ou un lecteur…');self.search.setClearButtonEnabled(True)
        row.addWidget(self.status);row.addWidget(self.search,1)
        layout.addLayout(row)
        self.preview=QPushButton('Voir le fichier');self.preview.clicked.connect(self.show_preview)
        self.analyse_button=QPushButton('Relancer avec un lecteur…');self.analyse_button.clicked.connect(self.analyse_with_reader)
        self.copy_button=QPushButton('Copier les non traités…');self.copy_button.clicked.connect(self.copy_unprocessed)
        self.export_button=QPushButton('Exporter la liste…');self.export_button.clicked.connect(self.export_list)
        self.ignore_button=QPushButton('Écarter du bilan');self.ignore_button.clicked.connect(self.toggle_ignored)
        self.remove_button=QPushButton('Supprimer…');self.remove_button.clicked.connect(self.remove_current)
        self.open_folder=QPushButton('Ouvrir les résultats');self.open_folder.clicked.connect(self.open_results)
        actions_row=QWidget();buttons=FlowLayout(actions_row)
        # A flow layout, so six actions wrap instead of forcing the window wider than
        # the 1024-pixel screens the desktop checks run on.
        for button in (self.preview,self.analyse_button,self.copy_button,self.export_button,self.ignore_button,
                       self.remove_button,self.open_folder):
            buttons.addWidget(button)
        layout.addWidget(actions_row)
        complete=QPushButton('Bilan complet');complete.clicked.connect(lambda:self.details.setPlainText(self._text))
        tail=QHBoxLayout();tail.addWidget(complete);tail.addStretch();layout.addLayout(tail)
        self.splitter=QSplitter(Qt.Vertical)
        self.table=QTableView();self.model=OutcomeModel(self)
        self.proxy=OutcomeFilter(self);self.proxy.setSourceModel(self.model)
        self.table.setModel(self.proxy);self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True);self.table.setWordWrap(False)
        self.table.verticalHeader().hide()
        self.table.setColumnWidth(0,190);self.table.setColumnWidth(1,330);self.table.setColumnWidth(2,130)
        self.table.setColumnWidth(3,230);self.table.horizontalHeader().setStretchLastSection(True)
        self.details=QTextBrowser();self.details.setOpenExternalLinks(False)
        self.splitter.addWidget(self.table);self.splitter.addWidget(self.details)
        self.splitter.setSizes([380,160]);layout.addWidget(self.splitter,1)
        self.status.currentIndexChanged.connect(self.filter)
        self.search.textChanged.connect(self.filter)
        self.table.selectionModel().currentChanged.connect(self.show_entry)
        self.table.doubleClicked.connect(lambda *_:self.show_preview())
        self.refresh_buttons()

    def summary_text(self):
        counts=Counter(outcome(e) for e in self.model.entries)
        # The template is translated before formatting, so the English entry can
        # be found: a formatted string never matches a table entry.
        head=translate("{} fichiers · {} réussis · {} à vérifier · {} erreurs/interrompus · "
                       "{} non reconnus/ignorés · {} autres/compagnons · {} écartés").format(
            len(self.model.entries),counts['complete'],counts['warnings'],counts['errors'],
            counts['unsupported'],counts['other'],counts['ignored'])
        tail=translate('Import : {} · {} analyses · Source : {}').format(
            translate(STATUSES.get(self.report['status'],self.report['status'])),
            len(self.report.get('documents',[])),self.report['source'])
        return head+'\n'+tail

    def set_report(self, report, text):
        self.report=report;self._text=text
        self.model.beginResetModel();self.model.entries=list(report.get('files',[])) if report else [];self.model.endResetModel()
        self.open_folder.setEnabled(report is not None)
        self.copy_button.setEnabled(report is not None)
        self.export_button.setEnabled(report is not None)
        self.refresh_buttons()
        if report:self.summary.setText(self.summary_text())
        else:self.summary.setText('Aucune collecte ouverte. Importez un dossier ou reprenez une collecte existante.')
        self.details.setPlainText(translate('Sélectionnez un fichier pour lire ses avertissements, sa provenance et ses sorties. '
            '« Voir le fichier » affiche un aperçu de son contenu, sans jamais modifier la preuve.') if report else text)
        self.filter()

    def refresh(self, report, text):
        """A collection that is still running: rows appear, states change.

        A reset at every file would drop the selection and the scroll position on
        every tick, so rows are only appended and the cells already shown are the
        only ones repainted.
        """
        self.report=report;self._text=text
        entries=list(report.get('files',[])) if report else []
        model=self.model
        shown=model.entries
        if len(entries)<len(shown) or any(entries[index] is not shown[index] for index in range(len(shown))):
            model.beginResetModel();model.entries=entries;model.endResetModel()
        elif len(entries)>len(shown):
            model.beginInsertRows(QModelIndex(),len(shown),len(entries)-1)
            model.entries=entries
            model.endInsertRows()
        else:
            model.entries=entries
            if entries:model.dataChanged.emit(model.index(0,0),model.index(len(entries)-1,model.columnCount()-1))
        self.open_folder.setEnabled(True);self.copy_button.setEnabled(True);self.export_button.setEnabled(True)
        self.summary.setText(self.summary_text())
        if self.proxy.status or self.proxy.query:self.filter()
        return True

    def filter(self, *_):
        self.proxy.status=self.status.currentData();self.proxy.query=self.search.text().strip().casefold()
        self.proxy.invalidate()

    def current_entry(self):
        current=self.table.currentIndex()
        if not current.isValid():return None
        return self.model.entries[self.proxy.mapToSource(current).row()]

    def refresh_buttons(self):
        entry=self.current_entry()
        usable=entry is not None and entry.get('status')!='deleted'
        self.preview.setEnabled(usable)
        self.analyse_button.setEnabled(usable and callable(self.on_analyse))
        self.ignore_button.setEnabled(usable)
        self.remove_button.setEnabled(usable)
        self.ignore_button.setText('Réintégrer au bilan' if entry and entry.get('ignored') else 'Écarter du bilan')

    def notify(self):
        if callable(self.on_changed):self.on_changed()

    def show_entry(self, current, *_):
        self.refresh_buttons()
        if not current.isValid():return
        entry=self.model.entries[self.proxy.mapToSource(current).row()]
        lines=[str(entry.get('path','')), 'État : '+STATUSES.get(entry['status'],entry['status'])]
        if entry.get('ignored'):lines+=['Écarté du bilan : décision de l\'analyste, le fichier reste décrit ici.']
        if entry.get('sha256'):lines+=['SHA-256 : '+entry['sha256']]
        if entry.get('error'):lines+=[entry['error']]
        for run in entry.get('runs',[]):
            lines+=['',run['tool']+' : '+STATUSES.get(run['status'],run['status']),run.get('error','')]
            lines+=run.get('warnings',[])
            for member in run.get('linux_logs', run.get('catscale',{})).get('members',[]):
                if member['status'] in ('error','unsupported','skipped'):
                    lines+=[member['status']+' · '+member['path']+' : '+member.get('reason','')]
            for output in run.get('outputs',[]):
                lines+=['Sortie : '+str(output.get('csv',''))]
        self.details.setPlainText('\n'.join(lines))

    def show_preview(self):
        entry=self.current_entry()
        if not entry:return
        self.details.setPlainText(str(entry.get('path',''))+'\n\n'+preview_text(entry.get('path','')))

    def analyse_with_reader(self):
        """Ask how to read this file, then hand the decision to the collection."""
        entry=self.current_entry()
        if not entry or not callable(self.on_analyse):return
        dialog=ReaderDialog(entry.get('path',''),self)
        accepted=dialog.exec()
        reader=dialog.reader()
        dialog.deleteLater()
        if accepted!=QDialog.DialogCode.Accepted:return
        self.on_analyse(str(entry.get('path','')),reader)

    def copy_unprocessed(self):
        if not self.report:return
        pending=[e for e in self.model.entries if outcome(e) in ('unsupported','errors')]
        if not pending:
            QMessageBox.information(self,'Rien à copier','Tous les fichiers ont été traités.')
            return
        destination=QFileDialog.getExistingDirectory(self,'Dossier de destination des fichiers non traités')
        if not destination:return
        result=actions.copy_unprocessed(pending,destination,self.report.get('source'))
        QMessageBox.information(self,'Copie terminée',translate(
            "{} fichiers copiés, {} déjà présents, {} échecs.\n\nDossier : {}").format(
            len(result['copied']),len(result['skipped']),len(result['failed']),result['destination']))
        if result['failed']:
            self.details.setPlainText('\n'.join(f'{path} : {reason}' for path,reason in result['failed']))

    def export_list(self):
        if not self.report:return
        target,_=QFileDialog.getSaveFileName(self,'Exporter la liste des fichiers','bilan-import.csv','CSV (*.csv)')
        if not target:return
        visible=[self.model.entries[self.proxy.mapToSource(self.proxy.index(row,0)).row()]
                 for row in range(self.proxy.rowCount())]
        actions.export_rows(visible,target,translate)
        QMessageBox.information(self,'Liste exportée',target)

    def toggle_ignored(self):
        entry=self.current_entry()
        if not entry:return
        actions.set_ignored(entry,not entry.get('ignored'))
        self.refresh_buttons();self.show_entry(self.table.currentIndex());self.notify()

    def remove_current(self):
        entry=self.current_entry()
        if not entry:return
        path=str(entry.get('path',''))
        answer=QMessageBox.warning(self,translate('Supprimer le fichier ?'),translate(
            "%s\n\nLe fichier sera supprimé du disque. Son empreinte SHA-256 restera dans le bilan, et la "
            "suppression est refusée si le fichier a changé depuis la collecte.\n\nContinuer ?")%path,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer!=QMessageBox.Yes:return
        try:
            record=actions.remove_source(entry)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self,'Suppression impossible',str(error));return
        entry.update(record)
        self.model.layoutChanged.emit();self.show_entry(self.table.currentIndex());self.notify()

    def open_results(self):
        if self.report:QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.report['output']))))

    def toPlainText(self):return self._text

    def setPlainText(self, text):
        self._text=text;self.details.setPlainText(text)
