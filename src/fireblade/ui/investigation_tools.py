"""Recovery, verified transport and evidence reports for case workspaces."""
import copy
from pathlib import Path
import base64

from PySide6.QtCore import QTimer, Qt, QBuffer, QIODevice
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit,
    QPushButton, QSpinBox, QVBoxLayout, QHBoxLayout)

from fireblade.core.case_package import export_package, import_package
from fireblade.core.investigation_report import build_report, write_report
from fireblade.core.workspace_reader import WorkspaceReader


class ReportDialog(QDialog):
    def __init__(self, parent, title):
        super().__init__(parent);self.setWindowTitle('Rapport d’investigation');self.resize(620,460)
        layout=QVBoxLayout(self);form=QFormLayout()
        self.title=QLineEdit(title);self.title.setMaxLength(500);form.addRow('Titre :',self.title)
        self.description=QPlainTextEdit();self.description.setPlaceholderText('Contexte, constatations et limites de votre investigation…')
        form.addRow('Synthèse :',self.description)
        self.bookmarks=QCheckBox('Uniquement les signets et notes');self.bookmarks.setChecked(True)
        self.filters=QCheckBox('Respecter les filtres de chaque analyse');self.filters.setChecked(True)
        self.selection=QCheckBox('Uniquement les lignes sélectionnées dans la grille active')
        self.timeline=QCheckBox('Ajouter la vue graphique courante de la chronologie')
        self.timeline.setEnabled(bool(getattr(parent,'timeline_panel',None) and parent.timeline_panel.store))
        self.limit=QSpinBox();self.limit.setRange(1,10000);self.limit.setValue(2000)
        form.addRow(self.bookmarks);form.addRow(self.filters);form.addRow(self.selection);form.addRow(self.timeline);form.addRow('Maximum de constats :',self.limit)
        layout.addLayout(form)
        hint=QLabel('Le rapport conserve les références aux lignes, les notes et les empreintes enregistrées à l’import. Les omissions et limites sont explicites. Aucune conclusion automatique n’est ajoutée.')
        hint.setWordWrap(True);layout.addWidget(hint)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)


class InvestigationToolsMixin:
    def investigation_destination_is_safe(self, path):
        if not self.export_destination_is_safe(path):return False
        data=self.active_investigation
        if data:
            target=Path(path).resolve();folder=self.investigation_library.folder(data['id'])
            if target==folder/'case.json' or target==folder/'timeline-state.json' or target==folder/'coverage-state.json' or target==folder/'coverage-last.json' or target.is_relative_to(folder/'History') or target.is_relative_to(folder/'IOC-hunts') or target.parent==folder and target.name.startswith('session-') and target.suffix=='.fireblade-session':
                self.error('L’export ne peut pas remplacer les fichiers de sauvegarde du case.');return False
        return True

    def setup_investigation_tools(self):
        self.investigation_task=None
        menu=self.menuBar().actions()[0].menu()
        menu.addSeparator()
        for label,method in [('Historique et récupération du case…',self.recover_investigation),
                             ('Exporter le case portable…',self.export_investigation_package),
                             ('Importer un case portable…',self.import_investigation_package),
                             ('Créer un rapport HTML / PDF…',self.export_investigation_report)]:
            action=QAction(label,self);action.triggered.connect(method);menu.addAction(action)
        self.autosave_action=QAction('Sauvegarde automatique du case (2 min)',self)
        self.autosave_action.setCheckable(True);self.autosave_action.setChecked(self.preferences.case_autosave);menu.addAction(self.autosave_action)
        self.autosave_action.toggled.connect(self.set_case_autosave)
        self.autosave_timer=QTimer(self);self.autosave_timer.setInterval(120000)
        self.autosave_timer.timeout.connect(self.autosave_investigation);self.autosave_timer.start()
        tools=QHBoxLayout()
        for label,method in [('Historique / récupération…',self.recover_investigation),
                             ('Exporter le case portable…',self.export_investigation_package),
                             ('Importer un case portable…',self.import_investigation_package)]:
            button=QPushButton(label);button.clicked.connect(method)
            tools.addWidget(button)
        self.cases_panel.layout().addLayout(tools)

    def set_case_autosave(self,enabled):
        from fireblade.core.preferences import save_preferences
        previous=self.preferences.case_autosave
        self.preferences.case_autosave=enabled
        try:save_preferences(self.preferences)
        except (OSError,ValueError) as exc:
            self.preferences.case_autosave=previous
            self.autosave_action.blockSignals(True);self.autosave_action.setChecked(previous);self.autosave_action.blockSignals(False)
            self.error('Préférence de sauvegarde non enregistrée : '+str(exc))

    def autosave_investigation(self):
        if not self.autosave_action.isChecked() or self.active_investigation is None:return
        if (self.busy or self.jobs or self.pool.activeThreadCount() or self.open_queue or
            getattr(self,'_collection_open_pending',False) or getattr(self,'_investigation_switching',False) or
            self.model and self.model.jobs):return
        self.persist_investigation(automatic=True)

    def recover_investigation(self):
        if not self.can_switch_investigation():return
        data=self.selected_investigation() or self.active_investigation
        if data is None:
            self.error('Sélectionnez un case dans le catalogue.');return
        versions=self.investigation_library.history(data['id'])
        if not versions:
            self.error('Aucune version de récupération disponible pour ce case.');return
        dialog=QDialog(self);dialog.setWindowTitle('Historique et récupération');dialog.resize(650,430)
        layout=QVBoxLayout(dialog)
        text=QLabel('Les dix dernières versions de session sont conservées. Restaurer retrouve les onglets, vues et métadonnées. Les annotations restent celles des bases actuelles ; les fichiers d’analyse ne sont pas dupliqués par cet historique.')
        text.setWordWrap(True);layout.addWidget(text)
        choices=QListWidget();layout.addWidget(choices)
        for version in versions:
            item=QListWidgetItem(f"{version['updated']} · {version['analysis_count']} analyse(s) · {version['name']}")
            item.setData(Qt.UserRole,version);choices.addItem(item)
        choices.setCurrentRow(0)
        buttons=QDialogButtonBox(QDialogButtonBox.RestoreDefaults|QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.RestoreDefaults).setText('Restaurer cette version')
        buttons.button(QDialogButtonBox.RestoreDefaults).clicked.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        try:
            if dialog.exec()!=QDialog.Accepted:return
            version=choices.currentItem().data(Qt.UserRole)
            session=self.investigation_library.session_path(version)
            if session:self.validate_session(session)
            active=self.active_investigation
            if active and active['id']!=data['id'] and not self.persist_investigation():return
            lease=None
            try:
                if not active or active['id']!=data['id']:
                    lease=self.investigation_library.lease(data['id']);lease.__enter__()
                result=self.investigation_library.restore(data['id'],version['revision'],
                    active['revision'] if active and active['id']==data['id'] else None)
            finally:
                if lease:lease.__exit__(None,None,None)
            if active and active['id']==data['id']:
                self.clear_investigation_workspace();self.active_investigation=None
            self.refresh_investigations()
            self.open_investigation(result['id'])
        except Exception as exc:self.error('Récupération impossible : '+str(exc))
        finally:dialog.deleteLater()

    def archive_and_release_selected(self):
        if not self.can_switch_investigation():return
        data=self.selected_investigation() or self.active_investigation
        if not data:return
        path,_=QFileDialog.getSaveFileName(self,'Archiver et libérer l’espace',data['name']+'.fireblade-case','Case (*.fireblade-case)')
        if not path:return
        if QMessageBox.question(self,'Libérer l’espace','Créer une archive vérifiée puis retirer les fichiers locaux du case ? Les sources externes sont conservées.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        if self.active_investigation and self.active_investigation['id']==data['id']:
            if not self.close_investigation():return
        from fireblade.core.case_storage import archive_and_release
        def done(result):
            self.cases_archived.setChecked(True)
            self.refresh_investigations()
            self.statusBar().showMessage(f"Archive vérifiée · {result['removed_bytes']/1024**2:.1f} Mio de fichiers locaux retirés")
        self.run(lambda:archive_and_release(self.investigation_library,data['id'],path,self.settings),done,exclusive=True)

    def restore_storage_case(self, data):
        from fireblade.core.case_storage import restore_archive
        def done(result):
            self.refresh_investigations()
            def reopen():
                if self.pool.activeThreadCount():QTimer.singleShot(30,reopen)
                else:self.open_investigation(result['case']['id'])
            QTimer.singleShot(0,reopen)
        self.run(lambda:restore_archive(self.investigation_library,data['id']),done,exclusive=True)

    def export_investigation_package(self, path=None, include_sources=None):
        if not self.can_switch_investigation():return
        if self.active_investigation is None:
            self.error('Ouvrez le case à transporter.');return
        if include_sources is None:
            dialog=QDialog(self);dialog.setWindowTitle('Transporter un case');layout=QVBoxLayout(dialog)
            text=QLabel('L’archive contient les analyses, annotations, vues et résultats de collecte. Les moteurs et DLL ne sont pas inclus. Les artefacts bruts d’une collecte doivent être conservés séparément pour relancer ses parseurs.')
            text.setWordWrap(True);layout.addWidget(text)
            sources=QCheckBox('Inclure les fichiers sources des analyses disponibles (peut être volumineux)');layout.addWidget(sources)
            buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
            buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
            accepted=dialog.exec()==QDialog.Accepted;include_sources=sources.isChecked();dialog.deleteLater()
            if not accepted:return
        if not path:path,_=QFileDialog.getSaveFileName(self,'Exporter le case portable','case.fireblade-case','Case portable (*.fireblade-case)')
        if not path or not self.investigation_destination_is_safe(path) or not self.save_investigation():return
        data=copy.deepcopy(self.active_investigation);documents=copy.deepcopy(self.documents);active=self.active_document;case=self.case
        def done(result):
            self.coverage_notice('Export','warning' if result['missing_sources'] else 'info',f"Case portable vérifié : {result['files']} fichiers ; {len(result['missing_sources'])} sources non incluses.",result['path'],missing_sources=result['missing_sources'])
            self.statusBar().showMessage(f"Archive vérifiée créée · {result['files']} fichiers · {len(result['missing_sources'])} source(s) non incluse(s) : {result['path']}")
        self.statusBar().showMessage('Création puis vérification SHA-256 de l’archive portable…')
        self.run(lambda:export_package(self.investigation_library,data,documents,active,path,
                                      include_sources=include_sources,active_case=case,settings=self.settings),done,exclusive=True,coverage_stage="Export",coverage_context=path)

    def import_investigation_package(self, path=None):
        if not self.can_switch_investigation():return
        if not path:path,_=QFileDialog.getOpenFileName(self,'Importer un case portable','','Case portable (*.fireblade-case)')
        if not path:return
        def done(result):
            self.refresh_investigations();self.show_investigations()
            self.statusBar().showMessage(f"Case importé : {result['case']['name']} · SHA-256 vérifiés · {len(result['missing_sources'])} source(s) à conserver séparément. Ouvrez-le depuis le catalogue.")
        self.statusBar().showMessage('Vérification de l’archive et import dans un nouveau case…')
        self.run(lambda:import_package(self.investigation_library,path),done,exclusive=True,coverage_stage="Import",coverage_context=path)

    def export_investigation_report(self):
        if not self.can_open_file():return
        if not self.documents:
            self.error('Ouvrez au moins une analyse.');return
        self.remember_active()
        dialog=ReportDialog(self,self.active_investigation['name'] if self.active_investigation else 'Rapport Fireblade')
        try:
            if dialog.exec()!=QDialog.Accepted:return
            self.coverage_panel.ensure_context()
            options=dict(coverage=copy.deepcopy(self.coverage_panel.report),bookmarks_only=dialog.bookmarks.isChecked(),respect_filters=dialog.filters.isChecked(),limit=dialog.limit.value())
            if options['coverage'] is not None:options['coverage']['stale']=self.coverage_panel.stale
            if dialog.timeline.isChecked():
                panel=self.timeline_panel
                viewport=panel.splitter.widget(0).viewport()
                buffer=QBuffer();buffer.open(QIODevice.WriteOnly)
                viewport.grab().save(buffer,'PNG')
                from fireblade.core.timeline import KINDS
                applied=panel.applied_filters
                caption='Vue visible de la chronologie, instantané après indexation. Corrélation : '+KINDS.get(applied.get('kind','text'),'Tout le texte')+' · '+(applied.get('text') or 'aucune')
                caption+=' · '+('valeur exacte' if applied.get('exact') else 'contient le texte')
                if applied.get('bookmarks'):caption+=' · signets uniquement'
                if panel.built_respect:caption+=' · filtres des analyses appliqués lors de la construction'
                if applied.get('start') is not None and applied.get('end') is not None:
                    from fireblade.core.timeline import utc_label
                    caption+=' · '+utc_label(applied['start'])+' — '+utc_label(applied['end'])
                caption+=' · Les pistes hors de la vue visible ne sont pas représentées dans cette capture.'
                if any(s['naive'] for s in panel.store.sources):caption+=' Les dates sans fuseau explicite sont positionnées comme UTC et doivent être vérifiées.'
                options['timeline']=dict(png=base64.b64encode(bytes(buffer.data())).decode('ascii'),caption=caption)
            if dialog.selection.isChecked():
                if self.model is None:self.error('Sélectionnez des enregistrements dans la grille.');return
                ids=[self.model.node(index).values[0] for index in self.tree.selectionModel().selectedRows() if not self.model.node(index).group]
                if not ids:self.error('Sélectionnez des enregistrements dans la grille.');return
                options['row_ids']={str(self.case.path):ids}
                options['bookmarks_only']=False
            title=dialog.title.text();description=dialog.description.toPlainText()
            path,_=QFileDialog.getSaveFileName(self,'Enregistrer le rapport','rapport.html','Rapport HTML (*.html);;Rapport PDF (*.pdf)')
            if not path:return
            if not self.investigation_destination_is_safe(path):return
            documents=[doc for doc in self.documents if 'row_ids' not in options or doc.path in options['row_ids']]
            reader=WorkspaceReader(documents,self.settings,self.case);self.investigation_task=reader
            def work():
                result=build_report(reader,title,description,**options)
                result['path']=write_report(path,result,reader.documents,pdf=Path(path).suffix.casefold()=='.pdf')
                return result
            def done(result):
                self.investigation_task=None
                self.coverage_notice('Export','warning' if result['errors'] or result.get('omitted') or result.get('abbreviated') else 'info',
                    f"Rapport : {result['records']} constats, {len(result['errors'])} erreurs, {result.get('omitted',0)} omissions, {result.get('abbreviated',0)} cellules abrégées.",result['path'],errors=result['errors'],omitted=result.get('omitted',0),abbreviated=result.get('abbreviated',0))
                self.statusBar().showMessage(f"Rapport créé : {result['records']} constats · {len(result['errors'])} analyse(s) en erreur · {result['path']}")
            def failed(message='Rapport annulé'):
                self.investigation_task=None;self.statusBar().showMessage(message)
            self.statusBar().showMessage('Création du rapport d’investigation…')
            self.run(work,done,exclusive=True,on_error=failed,on_cancel=failed,coverage_stage="Export",coverage_context=path)
        finally:dialog.deleteLater()
