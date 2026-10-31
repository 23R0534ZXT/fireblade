"""Desktop conveniences built on the existing paged model and worker queue."""
import copy
import json
from xml.etree.ElementTree import ParseError
from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QFileDialog,
    QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit, QVBoxLayout)
from fireblade.core.models import Filter
from fireblade.core.preferences import load_preferences, save_preferences, Preferences
from fireblade.ui.exploration_dialogs import DateFilterDialog, GroupsDialog
from fireblade.ui.preferences_dialog import PreferencesDialog
from fireblade.ui.cross_search import SearchDialog
from fireblade.ui.theme import apply_theme


class ExplorationMixin:
    def setup_exploration(self):
        self.workspace_search = None
        self.open_queue = []
        self.open_queue_timer_active = False
        self._expand_generation = 0
        self.message_lines = []
        self.message_window = None
        try:
            self.preferences = load_preferences()
        except (ValueError, TypeError, OSError) as exc:
            self.preferences = Preferences()
            self.statusBar().showMessage(f"Préférences ignorées : {exc}")
        self.statusBar().messageChanged.connect(self.record_message)
        self.apply_preferences()
        self.tree.frozen.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.frozen.customContextMenuRequested.connect(self.frozen_menu)
        self.tree.frozen.doubleClicked.connect(self.toggle_bookmark)
        self.tree.frozen.header().sectionResized.connect(lambda *_: self.capture_pin_widths())
        self.detail_fields = []
        self.details.setContextMenuPolicy(Qt.CustomContextMenu)
        self.details.customContextMenuRequested.connect(self.details_menu)
        self.tree.frozen.header().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.frozen.header().customContextMenuRequested.connect(self.frozen_header_menu)

    def apply_preferences(self):
        p = self.preferences
        apply_theme(QApplication.instance(), p.theme)
        font = QFont(p.font_family) if p.font_family else QApplication.font()
        font.setPointSizeF(p.font_size)
        QApplication.instance().setFont(font)
        self.splitter.setOrientation(Qt.Horizontal if p.details_position == "right" else Qt.Vertical)
        self.splitter.insertWidget(0,self.details if p.details_position=='top' else self.tree)
        self.splitter.setSizes([125,570] if p.details_position=='top' else [570,125])
        self.tabs.set_multiline(p.multiline_tabs)
        if self.model:
            self.model.date_format = p.date_format
            self.model.date_pattern = p.custom_date_format
            self.model.dark = p.theme == "dark"
            self.model.layoutChanged.emit()

    def edit_preferences(self):
        dialog = PreferencesDialog(self.preferences, self)
        if dialog.exec():
            try:
                save_preferences(dialog.preferences)
                self.preferences = dialog.preferences
                self.apply_preferences()
            except (OSError, ValueError) as exc:
                self.error(exc)
        dialog.deleteLater()

    def import_tle_settings(self):
        source,_=QFileDialog.getOpenFileName(self,'Importer les préférences TLE','TLE_settings.xml','Préférences TLE (*.xml)')
        if not source:return
        from fireblade.core.tle_settings import read_tle_settings
        try:
            result=read_tle_settings(source,self.preferences)
            save_preferences(result.preferences)
            self.preferences=result.preferences
            self.apply_preferences()
            self.statusBar().showMessage('Préférences TLE importées. '+' ; '.join(result.warnings))
        except (ValueError,TypeError,OSError,ParseError) as exc:self.error(exc)

    def visible_columns(self):
        header = self.tree.header()
        pinned = list(self.view.pinned_columns)
        return pinned + [section - 1 for position in range(header.count())
                         if (section := header.logicalIndex(position)) > 0
                         and section - 1 not in pinned and not self.tree.isColumnHidden(section)]

    def hide_column(self, column):
        if column in self.view.pinned_columns:
            self.pin_column(column)
        self.tree.setColumnHidden(column + 1, True)

    def pin_column(self, column):
        if column in self.view.pinned_columns:
            self.view.pinned_columns.remove(column)
        else:
            self.view.pinned_columns.append(column)
        # Keep line/group first so expansion and source IDs remain accessible.
        self.tree.set_pins([0] + [c + 1 for c in self.view.pinned_columns] if self.view.pinned_columns else [])

    def capture_pin_widths(self):
        if self.tree._syncing:
            return
        self.view.pinned_widths = {str(section): self.tree.frozen.columnWidth(section) for section in self.tree.pinned
                                   if self.tree.frozen.columnWidth(section) >= 20}

    def restore_pins(self):
        for section, width in self.view.pinned_widths.items():
            self.tree._widths[int(section)] = width
        self.tree.set_pins([0] + [c + 1 for c in self.view.pinned_columns] if self.view.pinned_columns else [])

    def reset_widths(self):
        if not self.model:
            return
        for column in range(self.model.columnCount()):
            width = 210 if column == 0 else 150
            self.tree.setColumnWidth(column, width)
            if column in self.tree.pinned:
                self.tree.frozen.setColumnWidth(column, width)

    def frozen_menu(self, position):
        from fireblade.ui.menus import cell_menu
        index = self.tree.frozen.indexAt(position)
        if self.copy_on_right_click(index):
            return
        menu = cell_menu(self, index)
        if menu:
            if not self.tree.selectionModel().isRowSelected(index.row(), index.parent()):
                self.tree.setCurrentIndex(index)
            menu.exec(self.tree.frozen.viewport().mapToGlobal(position))
            menu.deleteLater()

    def frozen_header_menu(self, position):
        from fireblade.ui.menus import header_menu
        header = self.tree.frozen.header()
        menu = header_menu(self, header.logicalIndexAt(position))
        if menu:
            menu.exec(header.mapToGlobal(position))
            menu.deleteLater()

    def copy_on_right_click(self, index):
        if (self.preferences.right_click_copy and not QApplication.keyboardModifiers() & Qt.ShiftModifier
                and self.model and index.isValid() and index.column() and not self.model.node(index).group):
            value = self.model.node(index).values[index.column()]
            QApplication.clipboard().setText("" if value is None else str(value))
            return True
        return False

    def edit_groups(self):
        if not self.case or self.busy:
            return
        dialog = GroupsDialog(self.case.headers, self.view, self)
        if dialog.exec():
            self.set_view(dialog.view)
        dialog.deleteLater()

    def group_interval(self, column, interval):
        self.view.group_intervals[str(column)] = interval
        self.group_column(column, append=True)

    def date_filter(self, column):
        dialog = DateFilterDialog(self)
        if dialog.exec():
            start, end = dialog.bounds()
            self.view.filters.extend([Filter(column, "after", start), Filter(column, "date_before", end)])
            self.apply()
        dialog.deleteLater()

    def clear_filters(self):
        view = copy.deepcopy(self.view)
        view.search, view.filters, view.expression, view.bookmarks_only = "", [], None, False
        self.set_view(view)

    def collapse_groups(self):
        self._expand_generation += 1
        if self.view.expand_all:
            view = copy.deepcopy(self.view)
            view.expand_all = False
            self.set_view(view)
            return
        self.tree.collapseAll()
        self.tree.frozen.collapseAll()

    def expand_groups(self):
        if not self.model or not self.view.groups or self.busy:
            return
        view = copy.deepcopy(self.view)
        view.expand_all = True
        self.set_view(view)
        self.statusBar().showMessage('Dépliage complet · index sur disque, navigation avec Suivant/Précédent ; annulation possible')

    def find_workspace(self):
        if not self.documents or not self.can_open_file():
            return
        dialog = SearchDialog(self)
        dialog.exec()
        self.workspace_search = None
        dialog.deleteLater()

    def choose_document(self):
        if not self.documents:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Analyses ouvertes")
        dialog.resize(600, 400)
        layout = QVBoxLayout(dialog)
        search, listing = QLineEdit(), QListWidget()
        search.setPlaceholderText("Filtrer les noms ou chemins")
        for i, doc in enumerate(self.documents):
            item = QListWidgetItem(Path(doc.source_info['path']).name)
            item.setData(Qt.UserRole, i)
            item.setToolTip(doc.path)
            listing.addItem(item)
        def filter_items(text):
            for i in range(listing.count()):
                item = listing.item(i)
                item.setHidden(text.casefold() not in (item.text() + item.toolTip()).casefold())
        search.textChanged.connect(filter_items)
        layout.addWidget(search)
        layout.addWidget(listing)
        listing.itemDoubleClicked.connect(lambda _item: dialog.accept())
        buttons = QDialogButtonBox(QDialogButtonBox.Open | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() and listing.currentItem():
            self.switch_document(listing.currentItem().data(Qt.UserRole))
        dialog.deleteLater()

    def reopen_closed(self):
        if not self.closed_documents or not self.can_open_file():
            return
        snapshot = self.closed_documents[-1]
        if any(d.path == snapshot.path for d in self.documents):
            self.closed_documents.pop()
            return
        self.documents.append(snapshot)
        self.switch_document(len(self.documents) - 1)
        if self.case and str(self.case.path) == snapshot.path:
            self.closed_documents.pop()
        else:
            self.documents.pop()
        self.sync_tabs()

    def record_message(self, text):
        if not text:
            return
        from datetime import datetime
        self.message_lines.append(datetime.now().strftime('%H:%M:%S') + '  ' + text[:2000])
        self.message_lines = self.message_lines[-500:]
        if self.message_window and self.message_window.isVisible():
            self.message_window.setPlainText('\n'.join(self.message_lines))

    def show_messages(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Messages")
        dialog.resize(800, 400)
        layout = QVBoxLayout(dialog)
        self.message_window = QPlainTextEdit('\n'.join(self.message_lines))
        self.message_window.setReadOnly(True)
        layout.addWidget(self.message_window)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()
        self.message_window = None
        dialog.deleteLater()

    def open_external(self, value, directory=False):
        """Only local paths; opening an executable selects it instead of running it."""
        path = Path(value).expanduser()
        if directory:
            path = path.parent if path.is_file() else path
        if not path.exists():
            self.error("Ce chemin n’existe pas sur ce poste.")
            return
        if path.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))
            return
        import subprocess
        import sys
        if sys.platform == "win32":
            subprocess.Popen(["explorer.exe", "/select,", str(path.resolve())])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent.resolve())))

    def export_layout(self):
        if not self.case:
            return
        target, _ = QFileDialog.getSaveFileName(self, "Exporter la disposition", "disposition.fireblade-view", "Vue Fireblade (*.fireblade-view)")
        if not target or not self.export_destination_is_safe(target):
            return
        import base64
        self.capture_pin_widths()
        view = copy.deepcopy(self.view)
        view.header_state = base64.b64encode(self.tree.header().saveState()).decode('ascii')
        payload = dict(format="fireblade-view", version=1, headers=self.case.headers, view=json.loads(view.to_json()))
        from fireblade.core.layout import write_json
        try:
            write_json(target, payload)
        except (OSError, ValueError) as exc:
            self.error(exc)

    def import_layout(self):
        if not self.case or self.busy:
            return
        source, _ = QFileDialog.getOpenFileName(self, "Importer une disposition", "", "Vues (*.fireblade-view *.layout *.local);;Tous les fichiers (*)")
        if not source:
            return
        from fireblade.core.layout import read_layout
        try:
            if Path(source).suffix.lower() in (".layout", ".local"):
                from fireblade.core.tle_layout import read_tle_layout
                layout = read_tle_layout(source, self.case.headers)
                columns, view = layout.columns, layout.view
                self.case.validate_view(view)
                self.tree.set_pins([])
                self.set_view(view)
                header = self.tree.header()
                for position, c in enumerate(sorted(columns, key=lambda c:c['position']),1):
                    section=c['column']+1
                    header.moveSection(header.visualIndex(section), min(position,header.count()-1))
                    self.tree.setColumnWidth(section,c['width'])
                    if c['column'] not in view.pinned_columns:
                        self.tree.setColumnHidden(section,c['position']<0)
                    else:
                        self.tree.frozen.setColumnWidth(section,c['width'])
                self.statusBar().showMessage('Layout TLE importé : colonnes, filtres, recherche, groupes, résumés et règles. '+ '; '.join(layout.warnings))
            else:
                self.set_view(read_layout(source, self.case.headers))
        except (OSError, ValueError, TypeError, KeyError, ParseError) as exc:
            self.error(exc)

    def edit_filter_text(self):
        if not self.case or self.busy:
            return
        text, accepted = QInputDialog.getMultiLineText(self, "Expression de filtre", "Syntaxe : Contains([Colonne], 'texte') And [ID] >= 10\nFonctions : Contains, Upper, Substring, Iif, IsNull, ToInt, Round, GetYear, AddDays, DateDiffDay… ; calculs, In, Between, Like, And, Or, Not.")
        if not accepted:
            return
        from fireblade.core.filter_text import parse_filter
        try:
            expression = parse_filter(text, self.case.headers)
            self.case.condition(expression)
            self.view.filters, self.view.expression = [], expression
            self.apply()
        except (ValueError, TypeError) as exc:
            self.error(exc)

    def manage_plugins(self):
        from fireblade.core.profiles import all_profiles
        from fireblade.core.profile_plugins import load_plugins, plugin_path, validate_plugin
        from fireblade.core.layout import write_json
        from PySide6.QtWidgets import QPushButton, QHBoxLayout
        dialog = QDialog(self)
        dialog.setWindowTitle("Profils et plugins de présentation")
        dialog.resize(680, 420)
        layout = QVBoxLayout(dialog)
        listing = QListWidget()
        layout.addWidget(listing)
        message = QLabel()
        message.setWordWrap(True)
        layout.addWidget(message)
        def refresh():
            listing.clear()
            for profile in all_profiles():
                listing.addItem(f"{profile.name} · {len(profile.signature)} champs de reconnaissance · {len(profile.timestamp)} dates · {len(profile.booleans)} booléens")
            _plugins, errors = load_plugins()
            message.setText('\n'.join(errors) if errors else "Les plugins de présentation déclarent les colonnes et leurs types. Les valeurs sources restent intactes.")
        def install():
            source, _ = QFileDialog.getOpenFileName(dialog, "Installer un plugin de présentation", "", "Plugin JSON (*.json)")
            if not source:
                return
            try:
                path = Path(source)
                if path.stat().st_size > 2 * 1024 * 1024:
                    raise ValueError('Plugin limité à 2 Mo')
                data = validate_plugin(json.loads(path.read_text(encoding='utf-8-sig')))
                import hashlib
                directory = plugin_path()
                directory.mkdir(parents=True, exist_ok=True)
                target = directory / (hashlib.sha256(data['name'].encode()).hexdigest()[:24] + '.json')
                write_json(target, data)
                refresh()
            except (ValueError, TypeError, OSError) as exc:
                message.setText(str(exc))
        row = QHBoxLayout()
        install_button = QPushButton("Installer un profil JSON…")
        install_button.clicked.connect(install)
        reload_button = QPushButton("Recharger")
        reload_button.clicked.connect(refresh)
        apply_button = QPushButton("Appliquer le profil détecté")
        apply_button.setEnabled(self.case is not None)
        apply_button.clicked.connect(self.apply_profile)
        for button in (install_button, reload_button, apply_button):
            row.addWidget(button)
        layout.addLayout(row)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(dialog.reject)
        layout.addWidget(close)
        refresh()
        dialog.exec()
        dialog.deleteLater()

    def show_legend(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Légende des supertimelines")
        layout = QVBoxLayout(dialog)
        for label, color in [("Exécution / registre", "#e2efda"), ("Ouverture de fichier / dossier", "#ddebf7"),
                             ("Suppression", "#fce4d6"), ("Navigation Web", "#fff2cc"), ("Journaux d’événements", "#e4dfec")]:
            text = QLabel(label)
            text.setStyleSheet(f"background: {color}; color: #202020; padding: 8px;")
            layout.addWidget(text)
        layout.addWidget(QLabel("Ces règles s’appliquent avec les profils de timeline reconnus.\nUne couleur ne prouve pas à elle seule la nature d’un événement."))
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(dialog.reject)
        layout.addWidget(close)
        dialog.exec()
        dialog.deleteLater()

    def import_tle_session(self, path=None):
        if not self.can_open_file():
            return
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Importer une session Timeline Explorer", "", "Session TLE (*.tle_sess)")
        if not path:
            return
        from fireblade.core.tle_compat import read_tle_session, TleSessionImport
        from fireblade.runtime.windows_paths import analyses_directory
        try:
            references = read_tle_session(path)
        except (ValueError, TypeError, OSError) as exc:
            self.error(exc)
            return
        snapshot = self.snapshot_analysis()
        task = TleSessionImport(references, analyses_directory(), self.settings,auto_profiles=self.preferences.auto_profiles)
        self.workspace_search = task
        self.detach()
        def failed(message="Import de session annulé"):
            self.workspace_search = None
            recovery = self.restore_after_import(snapshot)
            self.error(message + (f"\nRestauration : {recovery}" if recovery else ""))
        def done(snapshots):
            self.workspace_search = None
            self.documents, self.active_document = snapshots, -1
            self.sync_tabs()
            self.switch_document(0)
            self.statusBar().showMessage("Session TLE importée : sources et tags ; mises en page à importer séparément")
        self.run(task.run, done, exclusive=True, on_cancel=failed, on_error=failed)
        self.cancel_action.setEnabled(True)

    def mark_row(self, row_id, checked):
        if not self.case or self.busy:
            return
        case = self.case
        self.run(lambda: case.bookmark_many([row_id], '', 'mark' if checked else 'remove'), lambda _: self.apply(), exclusive=True)

    def details_menu(self, position):
        cursor = self.details.cursorForPosition(position)
        field = next((field for field in self.detail_fields if field[0] <= cursor.position() < field[1]), None)
        menu = self.details.createStandardContextMenu()
        if field and self.case:
            _start, _end, column, value = field
            menu.addSeparator()
            menu.addAction('Copier la valeur complète', lambda: QApplication.clipboard().setText('' if value is None else str(value)))
            menu.addAction('Filtrer sur ce champ', lambda: self.filter_value(column,value))
            menu.addAction('Exclure cette valeur', lambda: self.filter_value(column,value,exclude=True))
        menu.exec(self.details.mapToGlobal(position))
        menu.deleteLater()

    def open_with(self, value):
        path = Path(value).expanduser()
        if not path.exists():
            self.error('Ce chemin n’existe pas sur ce poste.')
            return
        program, _ = QFileDialog.getOpenFileName(self, 'Ouvrir avec', '', 'Programme Windows (*.exe);;Tous les fichiers (*)')
        if program:
            import subprocess
            try:
                subprocess.Popen([program,str(path.resolve())])
            except OSError as exc:
                self.error(exc)

    def queue_files(self, paths):
        self.open_queue.extend(Path(path) for path in paths)
        if len(self.open_queue) > 1000:
            self.open_queue = self.open_queue[:1000]
            self.statusBar().showMessage('File d’ouverture limitée à 1000 fichiers')
        self.drain_open_queue()

    def drain_open_queue(self):
        if self.open_queue_timer_active or not self.open_queue:
            return
        if self.busy or self.jobs or self.pool.activeThreadCount() or (self.model and self.model.jobs):
            self.open_queue_timer_active = True
            def retry():
                self.open_queue_timer_active = False
                self.drain_open_queue()
            QTimer.singleShot(50,retry)
            return
        path = self.open_queue.pop(0)
        self.open_path(path)
        if self.open_queue:
            QTimer.singleShot(0,self.drain_open_queue)

    def clear_open_queue(self):
        self.open_queue.clear()
        self.statusBar().showMessage('File d’ouverture vidée ; l’opération courante continue')
