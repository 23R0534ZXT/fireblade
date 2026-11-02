"""Investigation catalogue and explicit loading of one case workspace."""
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from fireblade.core.investigations import ENVIRONMENTS, STATUSES, InvestigationLibrary, now
from fireblade.runtime.windows_paths import user_directory


class InvestigationDialog(QDialog):
    def __init__(self, parent=None, data=None, adopt=False):
        super().__init__(parent)
        self.setWindowTitle('Modifier le case' if data else 'Nouveau case')
        self.resize(520,350)
        layout=QVBoxLayout(self);form=QFormLayout()
        self.name=QLineEdit((data or {}).get('name',''));self.name.setMaxLength(120)
        self.description=QPlainTextEdit((data or {}).get('description',''));self.description.setMaximumHeight(120)
        self.environment=QComboBox()
        for code,label in ENVIRONMENTS.items():self.environment.addItem(label,code)
        self.environment.setCurrentIndex(self.environment.findData((data or {}).get('environment','unspecified')))
        self.status=QComboBox()
        for code,label in STATUSES.items():self.status.addItem(label,code)
        self.status.setCurrentIndex(self.status.findData((data or {}).get('status','open')))
        form.addRow('Nom :',self.name);form.addRow('Description :',self.description)
        form.addRow('Collectes :',self.environment);form.addRow('Statut :',self.status)
        layout.addLayout(form)
        self.adopt=QCheckBox('Inclure les analyses actuellement ouvertes')
        self.adopt.setChecked(adopt);self.adopt.setVisible(adopt and data is None)
        layout.addWidget(self.adopt)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText('Enregistrer' if data else 'Créer le case')
        buttons.button(QDialogButtonBox.Ok).setEnabled(bool(self.name.text().strip()))
        self.name.textChanged.connect(lambda text:buttons.button(QDialogButtonBox.Ok).setEnabled(bool(text.strip())))
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)

    def values(self):
        return dict(name=self.name.text().strip(),description=self.description.toPlainText(),
                    environment=self.environment.currentData(),status=self.status.currentData())


class InvestigationMixin:
    def setup_investigations(self):
        self.investigation_library=InvestigationLibrary(self._investigation_root or user_directory()/'Cases')
        self.active_investigation=None
        self._active_investigation_lease=None
        self.investigation_collections=[]
        self._investigation_switching=False
        self._investigation_rows={}
        self._investigation_cache = None
        self.cases_panel=QWidget();layout=QVBoxLayout(self.cases_panel)
        title=QLabel('Cases — dossiers d’enquête');title.setStyleSheet('font-size: 18px; font-weight: bold;')
        layout.addWidget(title)
        text=QLabel('Retrouvez vos enquêtes et leur session. Seul le case que vous ouvrez charge ses analyses.')
        text.setWordWrap(True);layout.addWidget(text)
        controls=QHBoxLayout()
        for label,callback in [('Nouveau case…',self.new_investigation),('Ouvrir',self.open_selected_investigation),
                               ('Modifier…',self.edit_selected_investigation),('Archiver',self.archive_selected_investigation)]:
            button=QPushButton(label);button.clicked.connect(callback);controls.addWidget(button)
            if label=='Ouvrir':self.open_case_button=button
            if label=='Modifier…':self.edit_case_button=button
            if label=='Archiver':self.archive_case_button=button
        controls.addStretch();layout.addLayout(controls)
        filters=QHBoxLayout();self.cases_search=QLineEdit();self.cases_search.setPlaceholderText('Rechercher un nom, une description…')
        self.cases_search.textChanged.connect(lambda *_: self.refresh_investigations(reload=False))
        filters.addWidget(self.cases_search,1)
        self.cases_archived=QCheckBox('Inclure les archivés');self.cases_archived.toggled.connect(lambda *_: self.refresh_investigations(reload=False))
        filters.addWidget(self.cases_archived)
        refresh=QPushButton('Actualiser');refresh.clicked.connect(self.refresh_investigations);filters.addWidget(refresh)
        layout.addLayout(filters)
        self.cases_table=QTableWidget(0,7)
        self.cases_table.setHorizontalHeaderLabels(['Nom','Collectes','Statut','Analyses','Créé le','Modifié le','Dernière ouverture'])
        self.cases_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.cases_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.cases_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.cases_table.setAlternatingRowColors(True)
        self.cases_table.setWordWrap(False)
        self.cases_table.verticalHeader().hide()
        self.cases_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        for column,width in [(1,100),(2,130),(3,75),(4,145),(5,145),(6,145)]:self.cases_table.setColumnWidth(column,width)
        self.cases_table.setSortingEnabled(True)
        self.cases_table.sortItems(5,Qt.DescendingOrder)
        self.cases_table.itemDoubleClicked.connect(lambda *_:self.open_selected_investigation())
        self.cases_table.itemSelectionChanged.connect(self.show_investigation_details)
        layout.addWidget(self.cases_table,1)
        self.cases_details=QLabel('');self.cases_details.setTextFormat(Qt.PlainText);self.cases_details.setWordWrap(True)
        self.cases_details.setTextInteractionFlags(Qt.TextSelectableByMouse|Qt.TextSelectableByKeyboard)
        layout.addWidget(self.cases_details)
        active_row=QHBoxLayout()
        self.save_case_button=QPushButton('Enregistrer le case actif et sa session');self.save_case_button.clicked.connect(self.save_investigation)
        self.close_case_button=QPushButton('Fermer le case actif');self.close_case_button.clicked.connect(self.close_investigation)
        active_row.addWidget(self.save_case_button);active_row.addWidget(self.close_case_button);active_row.addStretch()
        layout.addLayout(active_row)
        self.cases_status=QLabel();self.cases_status.setTextFormat(Qt.PlainText);self.cases_status.setWordWrap(True)
        layout.addWidget(self.cases_status)
        self.cases_tab_index=self.workbench.addTab(self.cases_panel,'Cases')
        self.case_badge=QLabel();self.case_badge.setTextFormat(Qt.PlainText)
        self.case_badge.setMaximumWidth(230);self.case_badge.setMinimumWidth(0)
        self.workbench.setCornerWidget(self.case_badge,Qt.TopRightCorner)
        self.case_collection_panel=QWidget();row=QHBoxLayout(self.case_collection_panel);row.setContentsMargins(0,0,0,0)
        row.addWidget(QLabel('Collecte du case :'))
        self.case_collections_combo=QComboBox();self.case_collections_combo.setMinimumWidth(250)
        self.case_collections_combo.activated.connect(self.select_investigation_collection)
        row.addWidget(self.case_collections_combo,1)
        self.workbench.widget(1).layout().insertWidget(1,self.case_collection_panel)
        menu=self.menuBar().actions()[0].menu()
        anchor=menu.actions()[0]
        for label,callback,shortcut in [('Nouveau case…',self.new_investigation,'Ctrl+Alt+N'),('Cases…',self.show_investigations,None),
                                       ('Enregistrer le case et sa session',self.save_investigation,'Ctrl+Alt+S'),('Fermer le case',self.close_investigation,None)]:
            action=QAction(label,self);action.triggered.connect(callback)
            if label=='Enregistrer le case et sa session':self.save_case_action=action
            if label=='Fermer le case':self.close_case_action=action
            if shortcut:action.setShortcut(shortcut)
            menu.insertAction(anchor,action)
        menu.insertSeparator(anchor)
        self.main_toolbar.addSeparator()
        self.main_toolbar.addAction(self.save_case_action)
        self.last_case_save = QLabel()
        self.last_case_save.setTextFormat(Qt.PlainText)
        self.statusBar().addPermanentWidget(self.last_case_save)
        self.save_case_action.setText('Enregistrer le case')
        self.save_case_action.setToolTip('Sauvegarder le case actif et sa session (Ctrl+Alt+S). Les vues nommées restent indépendantes.')
        self.refresh_investigations();self.update_investigation_badge()
        self.show_investigations()

    def show_investigations(self):
        self.refresh_investigations();self.workbench.setCurrentIndex(self.cases_tab_index)

    def update_investigation_badge(self):
        if not hasattr(self,'case_badge'):return
        data=self.active_investigation
        self.case_badge.setText('Case : '+data['name'][:45] if data else 'Aucun case actif')
        self.case_badge.setToolTip(data['name'] if data else 'Ouvrez ou créez un dossier d’enquête dans Cases.')
        self.welcome_title.setText('Case : '+data['name'] if data else 'Commencer une analyse')
        self.welcome_title.setWordWrap(True)
        if data:
            stamp = datetime.fromisoformat(data['updated']).astimezone().strftime('%H:%M:%S')
            self.last_case_save.setText('Case enregistré à '+stamp)
            self.last_case_save.setToolTip('Dernière sauvegarde réussie du case et de sa session.')
        else:
            self.last_case_save.clear()
        self.save_case_button.setEnabled(data is not None);self.close_case_button.setEnabled(data is not None)
        self.save_case_action.setEnabled(data is not None);self.close_case_action.setEnabled(data is not None)
        self.case_collection_panel.setVisible(data is not None)

    def selected_investigation(self):
        row=self.cases_table.currentRow()
        item=self.cases_table.item(row,0) if row>=0 else None
        return self._investigation_rows.get(item.data(Qt.UserRole)) if item else None

    def refresh_investigations(self,*_, reload=True):
        if not hasattr(self,'cases_table'):return
        selected=self.selected_investigation()
        identifier=selected['id'] if selected else None
        if reload or self._investigation_cache is None:
            try:self._investigation_cache=self.investigation_library.list()
            except (OSError,ValueError) as exc:self._investigation_cache=([],[str(exc)])
        records,errors=self._investigation_cache
        query=self.cases_search.text().strip().casefold()
        self._investigation_rows={item['id']:item for item in records}
        visible=[item for item in records if (self.cases_archived.isChecked() or item['status']!='archived') and
                 (not query or query in (item['name']+' '+item['description']).casefold())]
        self.cases_table.blockSignals(True);self.cases_table.setSortingEnabled(False);self.cases_table.setRowCount(len(visible))
        for row,data in enumerate(visible):
            def date(value):
                return datetime.fromisoformat(value).astimezone().strftime('%Y-%m-%d %H:%M:%S') if value else '—'
            active=self.active_investigation is not None and self.active_investigation['id']==data['id']
            values=[data['name'],ENVIRONMENTS[data['environment']],STATUSES[data['status']]+(' · ouvert' if active else ''),
                    len(self.documents) if active else data['analysis_count'],date(data['created']),date(data['updated']),date(data['last_opened'])]
            for column,value in enumerate(values):
                item=QTableWidgetItem();item.setData(Qt.DisplayRole,value)
                item.setToolTip(data['name']+'\n'+data['description'] if column==0 else str(value))
                if column==0:
                    item.setData(Qt.UserRole,data['id'])
                    font=item.font();font.setBold(active);item.setFont(font)
                self.cases_table.setItem(row,column,item)
        self.cases_table.setSortingEnabled(True)
        self.cases_table.blockSignals(False)
        for row in range(self.cases_table.rowCount()):
            if self.cases_table.item(row,0).data(Qt.UserRole)==identifier:self.cases_table.selectRow(row);break
        self.cases_status.setText(f'{len(visible)} case(s) affiché(s)'+(' · Fiches indisponibles : '+' ; '.join(errors[:3]) if errors else ''))
        self.show_investigation_details()

    def show_investigation_details(self):
        data=self.selected_investigation()
        self.open_case_button.setEnabled(data is not None)
        self.edit_case_button.setEnabled(data is not None)
        self.archive_case_button.setEnabled(data is not None)
        self.archive_case_button.setText('Réactiver' if data and data['status']=='archived' else 'Archiver')
        self.cases_details.setText(data['name']+'\n'+(data['description'] or 'Aucune description.')+'\nDossier : '+str(self.investigation_library.folder(data['id'])) if data else 'Sélectionnez un case pour consulter sa description.')

    def can_switch_investigation(self):
        if not self.can_open_file():return False
        if self.open_queue:
            self.statusBar().showMessage('Terminez ou videz la file d’ouverture avant de changer de case.')
            return False
        return True

    def investigation_data_directory(self, name):
        if self.active_investigation is None:return None
        folder=self.investigation_library.folder(self.active_investigation['id'])/name
        folder.mkdir(parents=True,exist_ok=True)
        return folder

    def remember_investigation_collection(self):
        if self.active_investigation is None or self.collection is None:return
        path=str(self.collection.output)
        if not any(item['path']==path for item in self.investigation_collections):
            self.investigation_collections.append(dict(path=path,name=self.collection.root.name[:256]))
        self.refresh_investigation_collections()

    def refresh_investigation_collections(self):
        self.case_collections_combo.blockSignals(True);self.case_collections_combo.clear()
        for item in self.investigation_collections:self.case_collections_combo.addItem(item['name'],item['path'])
        if self.collection:self.case_collections_combo.setCurrentIndex(self.case_collections_combo.findData(str(self.collection.output)))
        self.case_collections_combo.blockSignals(False)
        self.refresh_navigation()

    def select_investigation_collection(self,index):
        if not self.can_open_file():return
        path=self.case_collections_combo.itemData(index)
        if not path:return
        from fireblade.core.collection import Collection
        try:
            candidate=Collection.reopen(path,self.toolpack(),self.settings)
            self.collection=candidate;self.show_collection_report(candidate.report)
            self.update_alert_context_bar()
        except Exception as exc:self.error(exc)
        self.refresh_investigation_collections()

    def persist_investigation(self, automatic=False):
        if self.active_investigation is None:return True
        try:
            latest=self.investigation_library.read(self.active_investigation['id'])
            if latest['revision'] != self.active_investigation['revision'] and all(
                latest[key]==self.active_investigation[key] for key in ('session','collections','active_collection')):
                # A metadata-only edit elsewhere must not discard the local view.
                self.active_investigation=latest
            self.remember_active()
            if self.collection:
                self.remember_investigation_collection()
                self.remember_collection_views()
            data=self.investigation_library.save(self.active_investigation['id'],self.documents,self.active_document,
                list(self.investigation_collections),str(self.collection.output) if self.collection else None,
                self.active_investigation['revision'])
            self.active_investigation=data
            self.update_investigation_badge();self.refresh_investigations()
            return True
        except Exception as exc:
            message='Le case n’a pas été enregistré : '+str(exc)
            if automatic:
                self.statusBar().showMessage('Sauvegarde automatique en erreur : '+str(exc))
                self.last_case_save.setText('Échec de la sauvegarde automatique')
                self.last_case_save.setToolTip(message)
            else:self.error(message)
            return False

    def save_investigation(self):
        if not self.can_open_file() or self.active_investigation is None:return False
        saved=self.persist_investigation()
        if saved:self.statusBar().showMessage('Case et session enregistrés : '+self.active_investigation['name'])
        return saved

    def clear_investigation_workspace(self):
        self.detach()
        if getattr(self,'timeline_panel',None):self.timeline_panel.reset_workspace()
        self.clear_context_preview()
        self.release_investigation_lease()
        self.documents=[];self.active_document=-1;self.closed_documents=[];self.sync_tabs()
        self.collection=None;self.investigation_collections=[]
        self._context_navigation=None;self._context_source_analysis=None;self._context_source_role=None
        self.refresh_investigation_collections();self.show_collection_report()

    def release_investigation_lease(self):
        if self._active_investigation_lease is not None:
            lease=self._active_investigation_lease
            self._active_investigation_lease=None
            lease.__exit__(None,None,None)

    def create_investigation(self, name, description='', environment='unspecified', status='open', adopt_workspace=None):
        if not self.can_switch_investigation():return None
        adopt=bool(self.documents) and self.active_investigation is None if adopt_workspace is None else adopt_workspace
        if adopt and self.active_investigation is not None:
            self.error('Fermez le case actif avant d’enregistrer cet espace dans un autre case.');return None
        if not self.persist_investigation():return None
        self._investigation_switching=True
        lease=None
        try:
            data=self.investigation_library.create(name,description,environment,status)
            lease=self.investigation_library.lease(data['id']);lease.__enter__()
            if not adopt:self.clear_investigation_workspace()
            self._active_investigation_lease=lease;lease=None
            self.active_investigation=data
            self.remember_investigation_collection()
            self.active_investigation=self.investigation_library.update(data['id'],data['revision'],last_opened=now())
            if not self.persist_investigation():return None
            self.workbench.setCurrentIndex(0)
            return self.active_investigation
        except Exception as exc:self.error(exc);return None
        finally:
            if lease is not None:lease.__exit__(None,None,None)
            self.finish_investigation_switch()

    def new_investigation(self):
        if not self.can_switch_investigation():return
        dialog=InvestigationDialog(self,adopt=bool(self.documents) and self.active_investigation is None)
        try:
            if dialog.exec()==QDialog.Accepted:self.create_investigation(**dialog.values(),adopt_workspace=dialog.adopt.isChecked())
        finally:dialog.deleteLater()

    def open_selected_investigation(self):
        data=self.selected_investigation()
        if data:self.open_investigation(data['id'])

    def open_investigation(self, identifier):
        if not self.can_switch_investigation():return False
        if self.active_investigation and self.active_investigation['id']==identifier:
            self.workbench.setCurrentIndex(0);return True
        self._investigation_switching=True
        candidate=None
        lease=None
        try:
            data=self.investigation_library.read(identifier)
            lease=self.investigation_library.lease(identifier);lease.__enter__()
            session=self.investigation_library.session_path(data)
            snapshots,active=self.validate_session(session) if session else ([], -1)
            if snapshots:candidate=self.prepare_snapshot(snapshots[active])
            # Validate the target before saving or closing the current workspace.
            if not self.persist_investigation():return False
            data=self.investigation_library.update(identifier,data['revision'],last_opened=now())
            self.clear_investigation_workspace()
            self._active_investigation_lease=lease;lease=None
            self.active_investigation=data
            self.investigation_collections=list(data['collections'])
            if data['active_collection']:
                from fireblade.core.collection import Collection
                try:self.collection=Collection.reopen(data['active_collection'],self.toolpack(),self.settings)
                except Exception as exc:self.statusBar().showMessage('Collecte indisponible : '+str(exc))
            self.documents=snapshots;self.active_document=-1;self.sync_tabs()
            if snapshots:
                snapshot=snapshots[active]
                self.attach(candidate,snapshot.view,snapshot.header_state,auto_layout=False)
                candidate=None
            self.refresh_investigation_collections()
            self.show_collection_report(self.collection.report if self.collection else None)
            self.update_investigation_badge();self.refresh_investigations();self.workbench.setCurrentIndex(0)
            return True
        except Exception as exc:self.error('Ouverture du case impossible : '+str(exc));return False
        finally:
            if candidate is not None and candidate is not self.case:self.connection_work(candidate.close)
            if lease is not None:lease.__exit__(None,None,None)
            self.finish_investigation_switch()

    def close_investigation(self):
        if not self.can_switch_investigation():return False
        if self.active_investigation is None:return True
        if not self.persist_investigation():return False
        self._investigation_switching=True
        try:
            self.clear_investigation_workspace();self.active_investigation=None
            self.update_investigation_badge();self.show_investigations()
            return True
        finally:self.finish_investigation_switch()

    def finish_investigation_switch(self):
        self._investigation_switching=False
        self.centralWidget().setEnabled(not self.busy)
        self.set_file_actions(self.model is not None and not self.busy)

    def edit_selected_investigation(self):
        data=self.selected_investigation()
        if data is None or not self.can_switch_investigation():return
        dialog=InvestigationDialog(self,data)
        try:
            if dialog.exec()!=QDialog.Accepted:return
            changes=dialog.values()
            if self.active_investigation and self.active_investigation['id']==data['id']:
                if changes['status']=='archived':
                    if not self.close_investigation():return
                elif not self.persist_investigation():return
            result=self.investigation_library.update(data['id'],**changes)
            if self.active_investigation and self.active_investigation['id']==data['id']:self.active_investigation=result
            self.update_investigation_badge();self.refresh_investigations()
        except Exception as exc:self.error(exc)
        finally:dialog.deleteLater()

    def archive_selected_investigation(self):
        data=self.selected_investigation()
        if data is None or not self.can_switch_investigation():return
        if self.active_investigation and self.active_investigation['id']==data['id']:
            if not self.close_investigation():return
        try:
            self.investigation_library.update(data['id'],status='open' if data['status']=='archived' else 'archived')
            self.refresh_investigations()
        except Exception as exc:self.error(exc)
