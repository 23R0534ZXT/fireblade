"""File opening, import recovery and drag/drop commands for the desktop."""
import copy
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog

from fireblade.core.engine import Case
from fireblade.core.models import AnalysisSnapshot, View
from fireblade.ui.dialogs import ImportDialog
from fireblade.ui.workers import Signals


class FileCommandsMixin:
    def import_csv(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Ouvrir des fichiers", "", "Données (*.csv *.tsv *.txt *.xlsx *.xls);;Tous les fichiers (*)")
        if paths:
            self.queue_files(paths)


    def dotnet_functions_loaded(self,names):
        self.apply()
        self.statusBar().showMessage('Fonctions chargées : '+', '.join(names))


    def load_dotnet_functions(self):
        if not self.case or self.busy:return
        from fireblade.core.tle_plugins import register_functions
        path,_=QFileDialog.getOpenFileName(self,'DLL contenant les fonctions Evaluate','','Bibliothèque .NET (*.dll)')
        if path:
            self.run(lambda:register_functions(self.case,path),self.dotnet_functions_loaded,exclusive=True)


    def import_with_tle_plugin(self):
        if not self.can_open_file():return
        from fireblade.core.tle_plugins import inspect_plugin
        from PySide6.QtWidgets import QInputDialog
        plugin,_=QFileDialog.getOpenFileName(self,'Choisir le plugin TLE et ses dépendances','','Plugin TLE (*.dll)')
        if not plugin:return
        def inspected(readers):
            if not readers:self.error('Aucun lecteur TLE public trouvé dans cette DLL');return
            labels=[r['description']+' · '+r['type'] for r in readers]
            choice,ok=QInputDialog.getItem(self,'Lecteur TLE','Lecteur :',labels,0,False)
            if not ok:return
            source,_=QFileDialog.getOpenFileName(self,'Source à traiter par le plugin','','Tous les fichiers (*)')
            if source:
                selected=(plugin,readers[labels.index(choice)]['type'])
                def start():
                    if self.pool.activeThreadCount():QTimer.singleShot(10,start)
                    else:self.import_file(source,selected)
                QTimer.singleShot(0,start)
        self.run(lambda:inspect_plugin(plugin),inspected,exclusive=True)


    def import_file(self, path, tle_plugin=None):
        if not self.can_open_file():
            return
        path = Path(path)
        if not path.is_file():
            self.error("Le fichier source est introuvable.")
            return
        if tle_plugin is None:
            from fireblade.core.reader_detection import detect_reader
            try:
                tle_plugin=self.connection_work(lambda:detect_reader(path),'Recherche d’un lecteur TLE par en-tête…')
            except Exception as exc:
                self.error(exc)
                return
        try:
            dialog = ImportDialog(path, self, plugin=True) if tle_plugin is not None else ImportDialog(path, self)
        except Exception as exc:
            self.error(exc)
            return
        if not dialog.exec():
            dialog.deleteLater()
            return
        target, delimiter, encoding = dialog.values()
        if target.exists():
            self.error("Choisissez un nouveau nom : une base existante ne sera pas écrasée.")
            return
        try:
            candidate = self.connection_work(lambda: Case(target, settings=self.settings))
        except Exception as exc:
            self.error(exc)
            return
        snapshot = self.snapshot_analysis()
        self.detach()
        self.case = candidate
        progress = Signals()
        progress.progress.connect(self.statusBar().showMessage)

        def cancelled():
            recovery_error = self.restore_after_import(snapshot)
            if recovery_error:
                self.error(f"Import annulé. Impossible de rouvrir l’analyse précédente :\n{recovery_error}")
            else:
                self.statusBar().showMessage("Import annulé. Analyse précédente rouverte." if snapshot else "Import annulé.")

        def failed(message):
            recovery_error = self.restore_after_import(snapshot)
            if recovery_error:
                message += f"\n\nImpossible de rouvrir l’analyse précédente :\n{recovery_error}"
            self.error(message)

        def importing():
            if tle_plugin is not None:
                from fireblade.core.tle_plugins import import_plugin
                import_plugin(candidate,path,*tle_plugin,progress.progress.emit)
                fields=candidate.info['plugin']['columns']
                view=View(boolean_columns=[i for i,c in enumerate(fields) if 'System.Boolean' in (c.get('type') or '')],timestamp_columns=[i for i,c in enumerate(fields) if 'System.DateTime' in (c.get('type') or '')])
                return ('Plugin TLE',view,None)
            if path.suffix.lower() in (".xlsx", ".xls"):
                candidate.import_excel(path, sheet, progress.progress.emit)
            else:
                candidate.import_csv(path, delimiter, encoding, progress.progress.emit)
            from fireblade.core.profiles import prepare_case_profile
            return prepare_case_profile(candidate,self.preferences.auto_profiles)
        def imported(result):
            self.coverage_notice("Import","warning" if not candidate.info["rows"] else "info",f"Import terminé : {candidate.info['rows']} lignes ; empreinte vérifiée avant et après lecture.",str(path),analysis=str(candidate.path),source_info=candidate.info)
            name,view,order=result
            if view is not None:
                wanted={n.casefold() for n in self.preferences.first_pinned_columns}
                view.pinned_columns=[i for i,h in enumerate(candidate.headers) if h.casefold() in wanted]
            self.attach(candidate,view,auto_layout=False)
            if order:
                header=self.tree.header()
                for position,column in enumerate(order,1):header.moveSection(header.visualIndex(column+1),position)
            if self.restore_format_layout():
                return
            if tle_plugin is not None:self.statusBar().showMessage('Plugin TLE exécuté ; source originale conservée et transformations tracées')
            elif name:self.statusBar().showMessage(f'Profil {name} détecté et appliqué ; valeurs sources intactes')
        sheet = dialog.sheet.currentText() if dialog.sheet is not None else None
        dialog.deleteLater()
        self.run(importing,imported,exclusive=True,on_cancel=cancelled,on_error=failed,coverage_stage="Import",coverage_context=str(path))


    def snapshot_analysis(self):
        if not self.case or not self.model:
            return None
        self.capture_pin_widths()
        return AnalysisSnapshot(str(self.case.path), copy.deepcopy(self.case.info),
                                copy.deepcopy(self.view), bytes(self.tree.header().saveState()))


    def restore_after_import(self, snapshot):
        """Close the failed importer before reopening the previous case's buffers."""
        self.detach()
        if snapshot is None:
            return None
        restored = None
        try:
            path = Path(snapshot.path)
            if not path.is_file():
                raise FileNotFoundError(f"Analyse introuvable : {path}")
            restored = self.connection_work(lambda: Case(path, settings=self.settings))
            if restored.info != snapshot.source_info:
                raise ValueError("L’analyse précédente a été remplacée par un autre jeu de données.")
            self.attach(restored, initial_view=snapshot.view, header_state=snapshot.header_state)
        except Exception as exc:
            if restored is not None:
                if self.case is restored:
                    self.detach()
                else:
                    self.connection_work(restored.close)
            return str(exc) or type(exc).__name__
        return None


    def open_path(self, path):
        path = Path(path)
        if path.suffix.lower() == ".fireblade-session":
            self.load_session(path)
        elif path.suffix.lower() == ".tle_sess":
            self.import_tle_session(path)
        elif path.suffix.lower() == ".timeline":
            self.load_case(path)
        else:
            self.import_file(path)


    @staticmethod
    def dropped_file(mime):
        urls = mime.urls() if mime.hasUrls() else []
        if len(urls) != 1 or not urls[0].isLocalFile():
            return None
        path = Path(urls[0].toLocalFile())
        if not path.is_file() or path.suffix.lower() not in (".csv", ".tsv", ".txt", ".xlsx", ".xls", ".timeline", ".fireblade-session", ".tle_sess"):
            return None
        return path


    @staticmethod
    def dropped_files(mime):
        urls = mime.urls() if mime.hasUrls() else []
        allowed = (".csv", ".tsv", ".txt", ".xlsx", ".xls", ".timeline", ".fireblade-session", ".tle_sess")
        if not urls or len(urls) > 1000 or any(not url.isLocalFile() for url in urls):
            return []
        paths = [Path(url.toLocalFile()) for url in urls]
        return paths if all(path.is_file() and path.suffix.lower() in allowed for path in paths) else []


    def dragEnterEvent(self, event):
        if self.dropped_files(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()


    def dropEvent(self, event):
        paths = self.dropped_files(event.mimeData())
        if not paths:
            event.ignore()
            return
        event.acceptProposedAction()
        # Let the OS finish the drop before displaying the import dialog.
        QTimer.singleShot(0, lambda: self.queue_files(paths))


    def open_case(self):
        if not self.can_open_file():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir une analyse", "", "Analyse (*.timeline);;Tous les fichiers (*)")
        if path:
            self.load_case(path)


    def load_case(self, path):
        if not self.can_open_file():
            return
        path = Path(path)
        if not path.is_file():
            self.error("L’analyse est introuvable.")
            return
        if self.case and path.resolve() == self.case.path:
            self.statusBar().showMessage("Cette analyse est déjà ouverte.")
            return
        try:
            candidate = self.connection_work(lambda: Case(path, settings=self.settings))
            if not candidate.headers:
                self.connection_work(candidate.close)
                raise ValueError("Base vide ou import inachevé")
        except Exception as exc:
            self.error(exc)
            return
        existing = next((i for i, doc in enumerate(self.documents) if doc.path == str(path.resolve())), -1)
        if existing >= 0:
            self.connection_work(candidate.close)
            self.switch_document(existing)
            return
        self.detach()
        self.attach(candidate)


