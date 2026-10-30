from __future__ import annotations

import copy
import base64
import json
import argparse
import sys
from xml.parsers.expat import ExpatError
from pathlib import Path

from PySide6.QtCore import QModelIndex, QThreadPool, QTimer, Qt, QEventLoop
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QSplitter, QStackedWidget, QStyle,
    QTreeView, QVBoxLayout, QWidget)

from fireblade.ui.dialogs import ImportDialog
from fireblade.core.engine import Case
from fireblade.ui.menus import cell_menu, header_menu
from fireblade.core.models import AnalysisSnapshot, Filter, FilterGroup, SortKey, View, OPERATORS
from fireblade.ui.advanced_dialogs import FilterDialog, RulesDialog, SortDialog
from fireblade.ui.grouping import GroupBar, GroupHeader
from fireblade.core.profiles import detect_profile, profile_view
from fireblade.ui.workspace import WorkspaceMixin
from fireblade.ui.shared_rules import SharedRulesMixin
from fireblade.ui.grid import GridDelegate, GridModel
from fireblade.core.settings import Settings, load_settings
from fireblade.ui.theme import apply_theme
from fireblade.ui.workers import Job, Signals
from fireblade.ui.exploration import ExplorationMixin
from fireblade.ui.pinned_grid import PinnedTree
from fireblade.runtime.resources import default_config
from fireblade.ui.help_dialogs import show_about, show_guide, show_licenses


class Window(ExplorationMixin, SharedRulesMixin, WorkspaceMixin, QMainWindow):
    def __init__(self, settings=None, rule_path=None):
        super().__init__()
        self.settings = settings or Settings()
        self.setWindowTitle("Fireblade")
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        self.resize(min(1280, max(640, int(available.width() * .9))) if available else 1280,
                    min(800, max(420, int(available.height() * .9))) if available else 800)
        self.case, self.model = None, None
        self.view = View()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.jobs = set()
        self.busy = False
        self.count_generation = 0
        self.build_ui()
        self.setup_workspace()
        self.setup_shared_rules(rule_path)
        self.setup_exploration()
        self.setAcceptDrops(True)

    def build_ui(self):
        file_menu = self.menuBar().addMenu("&Fichier")
        edit_menu = self.menuBar().addMenu("&Édition")
        view_menu = self.menuBar().addMenu("&Affichage")
        filter_menu = self.menuBar().addMenu("Fi&ltres")
        analysis_menu = self.menuBar().addMenu("A&nalyse")
        help_menu = self.menuBar().addMenu("A&ide")
        self.analysis_actions = []

        def action(menu, label, function, shortcut=None, requires_file=True, icon=None):
            item = QAction(label, self)
            item.triggered.connect(function)
            if shortcut:
                item.setShortcut(QKeySequence(shortcut))
            if icon is not None:
                item.setIcon(self.style().standardIcon(icon))
            menu.addAction(item)
            if requires_file:
                self.analysis_actions.append(item)
                item.setEnabled(False)
            return item

        open_csv = action(file_menu, "Ouvrir un fichier…", self.import_csv, "Ctrl+O", False, QStyle.SP_DialogOpenButton)
        action(file_menu, "Ouvrir une analyse…", self.open_case, "Ctrl+Shift+O", False)
        action(file_menu, 'Importer les préférences Timeline Explorer…', self.import_tle_settings,requires_file=False)
        action(file_menu, "Importer une session Timeline Explorer…", lambda: self.import_tle_session(), requires_file=False)
        action(file_menu, "Ouvrir une session…", lambda: self.load_session(), requires_file=False)
        action(file_menu, "Enregistrer la session…", lambda: self.save_session(), "Ctrl+Shift+S")
        action(file_menu, "Fermer l’onglet", lambda: self.close_document(self.active_document), "Ctrl+W")
        action(file_menu, "Vider la file d’ouverture", self.clear_open_queue, requires_file=False)
        action(file_menu, "Rouvrir le dernier onglet fermé", self.reopen_closed, "Ctrl+Shift+T", False)
        file_menu.addSeparator()
        export = action(file_menu, "Exporter…", self.export_csv, "Ctrl+E", icon=QStyle.SP_DialogSaveButton)
        action(file_menu, "Exporter les signets et notes…", self.export_annotations)
        file_menu.addSeparator()
        action(file_menu, "Quitter", self.close, "Alt+F4", False)
        action(edit_menu, "Copier les lignes", self.copy_rows, "Ctrl+C")
        action(edit_menu, "Signet / note…", lambda: self.toggle_bookmark(self.tree.currentIndex()))
        action(edit_menu, "Marquer la sélection", lambda: self.annotate_selection("mark"), "Ctrl+M")
        action(edit_menu, "Ajouter une note à la sélection…", lambda: self.annotate_selection("append"))
        action(edit_menu, "Remplacer les notes de la sélection…", lambda: self.annotate_selection("replace"))
        action(edit_menu, "Retirer les signets de la sélection", lambda: self.annotate_selection("remove"), "Ctrl+Shift+M")
        grouping = action(view_menu, "Regrouper…", self.group_by)
        action(view_menu, "Colonnes…", self.columns)
        action(view_menu, "Réinitialiser les largeurs", self.reset_widths, "Ctrl+R")
        action(view_menu, "Résumés et tri des groupes…", self.edit_groups)
        action(view_menu, "Déplier tous les groupes (vue paginée)", self.expand_groups, "Ctrl+Alt+M")
        action(view_menu, "Replier tous les groupes", self.collapse_groups, "Ctrl+K")
        action(view_menu, "Analyses ouvertes…", self.choose_document, "Ctrl+Shift+P", False)
        action(view_menu, "Messages…", self.show_messages, requires_file=False)
        action(view_menu, "Préférences…", self.edit_preferences, requires_file=False)
        view_menu.addSeparator()
        self.sort_action = action(view_menu, "Options de tri", lambda checked: self.sort_options.setVisible(checked), requires_file=False)
        self.sort_action.setCheckable(True)
        self.details_action = action(view_menu, "Détails de la ligne", lambda checked: self.details.setVisible(checked), requires_file=False)
        self.details_action.setCheckable(True)
        self.details_action.setChecked(True)
        action(view_menu, "Onglet suivant", lambda: self.next_document(), "Ctrl+Tab", False)
        action(view_menu, "Onglet précédent", lambda: self.next_document(-1), "Ctrl+Shift+Tab", False)
        action(view_menu, "Appliquer le profil détecté", self.apply_profile)
        action(view_menu, "Profils et plugins…", self.manage_plugins, requires_file=False)
        action(view_menu, "Légende des supertimelines…", self.show_legend, requires_file=False)
        action(view_menu, "Tri sur plusieurs colonnes…", self.edit_sort)
        action(filter_menu, "Expression textuelle…", self.edit_filter_text)
        action(filter_menu, "Éditeur ET / OU / NON…", self.edit_filters, "Ctrl+Shift+F")
        add_filter = action(filter_menu, "Ajouter un filtre…", self.add_filter)
        action(filter_menu, "Effacer les filtres", self.clear_filters, "Ctrl+Alt+E")
        action(filter_menu, "Réinitialiser", self.reset)
        action(filter_menu, "Rechercher dans toutes les analyses…", self.find_workspace, "Ctrl+F")
        action(analysis_menu, "Enregistrer la vue…", self.save_view, "Ctrl+S")
        action(analysis_menu, "Charger une vue…", self.load_view, "Ctrl+L")
        action(analysis_menu, "Exporter la disposition…", self.export_layout)
        action(analysis_menu, "Importer une disposition…", self.import_layout)
        analysis_menu.addSeparator()
        action(analysis_menu, "Règles de coloration…", self.edit_rules)
        global_menu = analysis_menu.addMenu("Règles globales")
        action(global_menu, "Modifier…", self.edit_global_rules, requires_file=False)
        action(global_menu, "Recharger depuis le disque", self.reload_global_rules, requires_file=False)
        action(global_menu, "Importer et remplacer…", lambda: self.import_global_rules(), requires_file=False)
        action(global_menu, "Exporter…", lambda: self.export_global_rules(), requires_file=False)
        self.global_rules_action = action(global_menu, "Appliquer à cette vue", self.toggle_global_rules)
        self.global_rules_action.setCheckable(True)
        self.global_rules_action.setChecked(True)
        action(analysis_menu, "Surligner un texte…", self.highlight)
        action(analysis_menu, "Afficher la cellule / JSON…", self.cell_details)
        action(analysis_menu, "Provenance et SHA-256…", self.integrity)
        analysis_menu.addSeparator()
        from fireblade.ui.derived_columns import edit_derived, quality
        action(analysis_menu, 'Convertir une date…', lambda: edit_derived(self))
        action(analysis_menu, 'Ajouter une colonne calculée…', lambda: edit_derived(self,expression=True))
        action(analysis_menu, 'Contrôler les colonnes dérivées…', lambda: quality(self))
        self.cancel_action = action(analysis_menu, "Interrompre la requête", self.interrupt_queries, requires_file=False)
        self.cancel_action.setEnabled(False)
        action(help_menu, "Guide d’utilisation", lambda: show_guide(self), "F1", False)
        action(help_menu, "Licences", lambda: show_licenses(self), requires_file=False)
        action(help_menu, "À propos de Fireblade", lambda: show_about(self), requires_file=False)

        toolbar = self.addToolBar("Fichier")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        toolbar.addAction(open_csv)
        toolbar.addAction(export)
        toolbar.addSeparator()
        toolbar.addAction(add_filter)
        toolbar.addAction(grouping)

        self.content_stack = QStackedWidget()
        welcome = QWidget()
        welcome_layout = QVBoxLayout(welcome)
        welcome_layout.addStretch()
        message = QLabel("Aucun fichier ouvert.")
        message.setAlignment(Qt.AlignCenter)
        welcome_layout.addWidget(message)
        open_button = QPushButton("Ouvrir un CSV…")
        open_button.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        open_button.clicked.connect(self.import_csv)
        welcome_layout.addWidget(open_button, 0, Qt.AlignHCenter)
        welcome_layout.addStretch()
        self.content_stack.addWidget(welcome)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self.source = QLabel()
        self.statusBar().addPermanentWidget(self.source)
        self.rules_summary = QLabel()
        self.statusBar().addPermanentWidget(self.rules_summary)
        row = QHBoxLayout()
        row.addWidget(QLabel("Rechercher :"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Toutes les colonnes · Entrée pour appliquer")
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(self.apply)
        row.addWidget(self.search, 1)
        clear = QPushButton("Réinitialiser")
        clear.clicked.connect(self.reset)
        row.addWidget(clear)
        self.only_notes = QCheckBox("Signets")
        self.only_notes.toggled.connect(self.apply)
        row.addWidget(self.only_notes)
        layout.addLayout(row)
        self.filters = QListWidget()
        self.filters.setMaximumHeight(90)
        self.filters.setToolTip("Double-clic pour retirer un filtre")
        self.filters.itemDoubleClicked.connect(self.remove_filter)
        layout.addWidget(self.filters)
        self.filters.hide()
        self.sort_options = QWidget()
        sortrow = QHBoxLayout(self.sort_options)
        sortrow.setContentsMargins(0, 0, 0, 0)
        sortrow.addWidget(QLabel("Tri :"))
        self.sort_column = QComboBox()
        self.sort_column.addItem("Ordre source", None)
        self.sort_column.activated.connect(self.apply)
        sortrow.addWidget(self.sort_column)
        self.sort_type = QComboBox()
        for label, value in [("Texte", "text"), ("Nombre", "number"), ("Date ISO", "timestamp")]:
            self.sort_type.addItem(label, value)
        self.sort_type.activated.connect(self.apply)
        sortrow.addWidget(self.sort_type)
        self.desc = QCheckBox("Décroissant")
        self.desc.toggled.connect(self.apply)
        sortrow.addWidget(self.desc)
        sortrow.addStretch()
        layout.addWidget(self.sort_options)
        self.sort_options.hide()
        group_row = QHBoxLayout()
        self.groups_label = GroupBar(self.group_column)
        group_row.addWidget(self.groups_label, 1)
        change_groups = QPushButton("Regrouper…")
        change_groups.clicked.connect(self.group_by)
        group_row.addWidget(change_groups)
        layout.addLayout(group_row)
        splitter = self.splitter = QSplitter(Qt.Vertical)
        self.tree = PinnedTree()
        self.tree.setItemDelegate(GridDelegate(self.tree))
        self.tree.setHeader(GroupHeader(self.tree))
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionBehavior(QTreeView.SelectRows)
        self.tree.setSelectionMode(QTreeView.ExtendedSelection)
        self.tree.setHorizontalScrollMode(QTreeView.ScrollPerPixel)
        self.tree.setAnimated(False)
        self.tree.setIndentation(16)
        self.tree.header().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.tree.header().setMinimumHeight(max(26, self.fontMetrics().height() + 8))
        self.tree.doubleClicked.connect(self.toggle_bookmark)
        self.tree.expanded.connect(lambda index: self.model.fetchMore(index) if self.model and not self.model.node(index).children else None)
        self.tree.collapsed.connect(lambda index: self.model.unload(index) if self.model else None)
        self.tree.header().sectionClicked.connect(self.header_sort)
        self.tree.header().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.header().customContextMenuRequested.connect(self.show_header_menu)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_cell_menu)
        self.tree.setToolTip("Double-clic : signet et note. Dépliez un groupe pour explorer ses lignes.")
        splitter.addWidget(self.tree)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Détails de la ligne sélectionnée")
        splitter.addWidget(self.details)
        splitter.setSizes([570, 125])
        layout.addWidget(splitter, 1)
        pager = QHBoxLayout()
        root_button = QPushButton("Racine")
        root_button.clicked.connect(lambda: self.tree.setCurrentIndex(QModelIndex()))
        pager.addWidget(root_button)
        previous = QPushButton("Précédent")
        previous.setToolTip(f"Revenir de {self.settings.max_loaded_rows} éléments")
        previous.clicked.connect(self.previous)
        pager.addWidget(previous)
        more = QPushButton("Suivant")
        more.setToolTip(f"Charger {self.settings.page_size} éléments dans le groupe sélectionné")
        more.clicked.connect(self.more)
        pager.addWidget(more)
        pager.addStretch()
        self.count_label = QLabel()
        pager.addWidget(self.count_label)
        layout.addLayout(pager)
        self.content_stack.addWidget(body)
        self.setCentralWidget(self.content_stack)
        self.statusBar().showMessage("Prêt")

    def set_file_actions(self, enabled):
        for item in self.analysis_actions:
            item.setEnabled(enabled)

    def error(self, message):
        self.statusBar().showMessage("Opération interrompue ou en erreur")
        QMessageBox.warning(self, "Opération impossible", str(message))

    def interrupt_queries(self):
        self._expand_generation += 1
        if self.workspace_search:
            self.workspace_search.interrupt()
        for job in tuple(self.jobs):
            job.cancel()
        if self.model:
            for job in tuple(self.model.jobs):
                job.cancel()
        if self.case:
            self.case.interrupt()
        self.statusBar().showMessage("Annulation demandée…")

    def run(self, fn, done, exclusive=False, on_cancel=None, on_error=None):
        if exclusive and self.busy:
            return
        if exclusive:
            self.busy = True
            self.centralWidget().setEnabled(False)
            self.set_file_actions(False)
            self.cancel_action.setEnabled(self.case is not None)
        job = Job(fn)
        self.jobs.add(job)
        released = False
        def release():
            nonlocal released
            if released:return False
            released = True
            self.jobs.discard(job)
            job.signals.done.disconnect(finish)
            job.signals.error.disconnect(fail)
            job.signals.cancelled.disconnect(was_cancelled)
            job.signals.progress.disconnect()
            if exclusive:
                self.busy = False
                self.centralWidget().setEnabled(True)
                self.set_file_actions(self.model is not None)
            return True

        def finish(value):
            if not release():return
            done(value)

        def fail(message):
            if not release():return
            if on_error:
                on_error(message)
            else:
                self.error(message)

        def was_cancelled():
            if not release():return
            self.statusBar().showMessage("Opération annulée.")
            if on_cancel:
                on_cancel()

        job.signals.done.connect(finish)
        job.signals.error.connect(fail)
        job.signals.cancelled.connect(was_cancelled)
        job.signals.progress.connect(self.statusBar().showMessage)
        self.pool.start(job)
        return job

    def connection_work(self, function, message='Ouverture de l’analyse…'):
        """Keep Windows painting/timers alive during native connect/checkpoint.

        A local event loop preserves the existing synchronous ownership protocol;
        all controls that could mutate the workspace stay disabled until return.
        The serialized pool owns the actual DuckDB call.
        """
        loop = QEventLoop(self)
        previous_busy = self.busy
        previous_cancel = self.cancel_action.isEnabled()
        self.cancel_action.setEnabled(False)
        self.busy = True
        self.centralWidget().setEnabled(False)
        self.set_file_actions(False)
        self.statusBar().showMessage(message)
        result, errors = [], []
        job = Job(function)
        def done(value):
            result.append(value)
            loop.quit()
        def failed(error):
            errors.append(error)
            loop.quit()
        job.signals.done.connect(done)
        job.signals.error.connect(failed)
        job.signals.cancelled.connect(lambda: failed('Opération annulée'))
        self.jobs.add(job)
        try:
            self.pool.start(job)
            loop.exec()
        finally:
            self.jobs.discard(job)
            job.signals.done.disconnect()
            job.signals.error.disconnect()
            job.signals.cancelled.disconnect()
            self.busy = previous_busy
            self.cancel_action.setEnabled(previous_cancel)
            self.centralWidget().setEnabled(not previous_busy)
            self.set_file_actions(self.model is not None and not previous_busy)
            loop.deleteLater()
        if errors:
            raise RuntimeError(errors[0])
        return result[0]

    def can_open_file(self):
        if self.busy or self.pool.activeThreadCount() or self.jobs or (self.model and self.model.jobs):
            self.statusBar().showMessage("Attendez ou interrompez la requête avant de changer d’analyse.")
            return False
        return True

    def import_csv(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Ouvrir des fichiers", "", "Données (*.csv *.tsv *.txt *.xlsx *.xls);;Tous les fichiers (*)")
        if paths:
            self.queue_files(paths)

    def import_file(self, path):
        if not self.can_open_file():
            return
        path = Path(path)
        if not path.is_file():
            self.error("Le fichier source est introuvable.")
            return
        try:
            dialog = ImportDialog(path, self)
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
            if path.suffix.lower() in (".xlsx", ".xls"):
                return candidate.import_excel(path, sheet, progress.progress.emit)
            return candidate.import_csv(path, delimiter, encoding, progress.progress.emit)
        sheet = dialog.sheet.currentText() if dialog.sheet is not None else None
        dialog.deleteLater()
        self.run(importing,
                 lambda _: self.attach(candidate), exclusive=True, on_cancel=cancelled, on_error=failed)

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

    def detach(self):
        self.remember_active()
        # Never close a connection while a queued page request still refers to it.
        self.count_generation += 1
        if self.model:
            self.model.generation += 1
        self.pool.waitForDone()
        if self.case:
            self.connection_work(self.case.close, 'Fermeture de l’analyse · enregistrement sur disque…')
        self.tree.setModel(None)
        if self.model:
            self.model.deleteLater()
        self.case, self.model = None, None
        self.content_stack.setCurrentIndex(0)
        self.source.clear()
        self.rules_summary.clear()
        self.set_file_actions(False)
        self.cancel_action.setEnabled(False)
        self.setWindowTitle("Fireblade")

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

    def attach(self, case, initial_view=None, header_state=None):
        self.case = case
        self.content_stack.setCurrentIndex(1)
        self.set_file_actions(True)
        self.cancel_action.setEnabled(True)
        self.model = GridModel(case, self.pool, self)
        self.model.date_format = self.preferences.date_format
        self.model.date_pattern = self.preferences.custom_date_format
        self.model.dark = self.preferences.theme == "dark"
        self.model.bookmark_requested.connect(self.mark_row)
        self.model.status.connect(self.statusBar().showMessage)
        self.model.error.connect(self.error)
        self.tree.setModel(self.model)
        self.tree.selectionModel().currentChanged.connect(self.show_details)
        self.tree.header().setSectionsMovable(True)
        self.tree.header().setSectionResizeMode(QHeaderView.Interactive)
        for i in range(self.model.columnCount()):
            self.tree.setColumnHidden(i, False)
            self.tree.header().moveSection(self.tree.header().visualIndex(i), i)
            self.tree.setColumnWidth(i, 210 if i == 0 else 150)
        self.sort_column.blockSignals(True)
        self.sort_column.clear()
        self.sort_column.addItem("Ordre source", None)
        for i, h in enumerate(case.headers):
            self.sort_column.addItem(h, i)
        self.sort_column.blockSignals(False)
        name = Path(case.info["path"]).name
        self.setWindowTitle(f"{name} - Fireblade")
        self.source.setText(f"{name}  |  {len(case.headers)} colonnes")
        if initial_view is None:
            initial_view=View(pinned_columns=[i for i,h in enumerate(case.headers) if h.casefold() in {name.casefold() for name in self.preferences.first_pinned_columns}])
        self.set_view(initial_view)
        if header_state is not None:
            self.tree.header().restoreState(header_state)
        self.restore_pins()
        self.track_case()

    def apply(self, *_):
        if not self.case or not self.model or self.busy:
            return
        try:
            self.case.validate_view(self.view)
        except ValueError as exc:
            self.error(exc)
            return
        self.view.search = self.search.text()
        self.view.bookmarks_only = self.only_notes.isChecked()
        self.view.sort_column = self.sort_column.currentData()
        self.view.sort_type = self.sort_type.currentData()
        self.view.descending = self.desc.isChecked()
        if self.view.sorts and (self.view.sorts[0].column, self.view.sorts[0].kind, self.view.sorts[0].descending) != (self.view.sort_column, self.view.sort_type, self.view.descending):
            self.view.sorts = []
        self.filters.clear()
        for f in self.view.filters:
            label = dict((v, k) for k, v in OPERATORS)[f.operator]
            self.filters.addItem(f"{self.case.headers[f.column]}  {label}  {f.value}")
        if self.view.expression is not None:
            self.filters.addItem("Expression ET / OU / NON · ouvrir l’éditeur pour modifier")
        self.filters.setVisible(bool(self.view.filters) or self.view.expression is not None)
        self.groups_label.setText("Groupement : " + " > ".join(self.case.headers[i] for i in self.view.groups) if self.view.groups else "Glissez un en-tête ici pour regrouper")
        section = self.view.sort_column
        self.tree.header().setSortIndicatorShown(section is not None)
        if section is not None:
            self.tree.header().setSortIndicator(section + 1, Qt.DescendingOrder if self.view.descending else Qt.AscendingOrder)
        self.global_rules_action.blockSignals(True)
        self.global_rules_action.setChecked(self.view.global_rules_enabled)
        self.global_rules_action.blockSignals(False)
        self._expand_generation += 1
        self.model.reset(self.view, self.global_rules_for_view())
        self.detail_fields = []
        self.details.clear()
        self.count_generation += 1
        generation = self.count_generation
        view = copy.deepcopy(self.view)
        case = self.case
        self.count_label.setText("Comptage…")
        # Obsolete queued counts need not scan a large case before the latest view.
        self.run(lambda: case.count(view) if generation == self.count_generation else None,
                 lambda n: self.count_label.setText(f"{n:,} / {case.info['rows']:,} lignes") if generation == self.count_generation else None,
                 on_cancel=lambda: self.count_label.setText("Comptage interrompu") if generation == self.count_generation else None)

    def reset(self):
        self.tree.set_pins([])
        self.set_view(View())

    def set_view(self, view):
        if self.case:
            try:
                self.case.validate_view(view)
            except (ValueError, TypeError) as exc:
                self.error(exc)
                return
        self.view = copy.deepcopy(view)
        if self.view.sorts:
            first = self.view.sorts[0]
            self.view.sort_column, self.view.sort_type, self.view.descending = first.column, first.kind, first.descending
        widgets = [self.search, self.only_notes, self.sort_column, self.sort_type, self.desc]
        previous = [widget.blockSignals(True) for widget in widgets]
        self.search.setText(self.view.search)
        self.only_notes.setChecked(self.view.bookmarks_only)
        self.sort_column.setCurrentIndex(self.sort_column.findData(self.view.sort_column))
        self.sort_type.setCurrentIndex(self.sort_type.findData(self.view.sort_type))
        self.desc.setChecked(self.view.descending)
        for widget, blocked in zip(widgets, previous):
            widget.blockSignals(blocked)
        self.apply()
        self.restore_pins()
        if self.view.header_state:
            try:
                self.tree.header().restoreState(base64.b64decode(self.view.header_state, validate=True))
            except ValueError:
                self.statusBar().showMessage("Disposition des colonnes invalide ; disposition par défaut conservée")

    def add_filter(self, column_index=None):
        if not self.case or self.busy:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Ajouter un filtre · ET logique")
        form = QFormLayout(dialog)
        column, operator, value = QComboBox(), QComboBox(), QLineEdit()
        column.addItems(self.case.headers)
        if type(column_index) is int and 0 <= column_index < len(self.case.headers):
            column.setCurrentIndex(column_index)
        for label, code in OPERATORS:
            operator.addItem(label, code)
        form.addRow("Colonne", column)
        form.addRow("Condition", operator)
        form.addRow("Valeur", value)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec():
            self.view.filters.append(Filter(column.currentIndex(), operator.currentData(), value.text()))
            self.apply()

    def remove_filter(self, item):
        index = self.filters.row(item)
        if index >= len(self.view.filters):
            self.edit_filters()
            return
        del self.view.filters[index]
        self.apply()

    def group_by(self):
        if not self.case:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Regrouper · ordre des niveaux de haut en bas")
        layout = QVBoxLayout(dialog)
        listing = QListWidget()
        listing.setDragDropMode(QListWidget.InternalMove)
        order = self.view.groups + [i for i in range(len(self.case.headers)) if i not in self.view.groups]
        from PySide6.QtWidgets import QListWidgetItem
        for i in order:
            item = QListWidgetItem(self.case.headers[i])
            item.setData(Qt.UserRole, i)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if i in self.view.groups else Qt.Unchecked)
            listing.addItem(item)
        layout.addWidget(QLabel("Cochez les colonnes et glissez-les pour ordonner les niveaux."))
        layout.addWidget(listing)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec():
            self.view.groups = [listing.item(i).data(Qt.UserRole) for i in range(listing.count()) if listing.item(i).checkState() == Qt.Checked]
            self.apply()

    def columns(self):
        if not self.case:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Colonnes visibles")
        layout = QVBoxLayout(dialog)
        checks = []
        listing = QListWidget()
        from PySide6.QtWidgets import QListWidgetItem
        for i, label in enumerate(self.case.headers, 1):
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked if self.tree.isColumnHidden(i) and i - 1 not in self.view.pinned_columns else Qt.Checked)
            listing.addItem(item)
            checks.append(item)
        layout.addWidget(listing)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec():
            for i, item in enumerate(checks, 1):
                if item.checkState() != Qt.Checked:
                    self.hide_column(i - 1)
                elif i - 1 not in self.view.pinned_columns:
                    self.tree.setColumnHidden(i, False)

    def show_header_menu(self, position):
        header = self.tree.header()
        menu = header_menu(self, header.logicalIndexAt(position))
        if menu:
            menu.exec(header.mapToGlobal(position))
            menu.deleteLater()

    def show_cell_menu(self, position):
        index = self.tree.indexAt(position)
        if self.copy_on_right_click(index):
            return
        menu = cell_menu(self, index)
        if menu:
            if not self.tree.selectionModel().isRowSelected(index.row(), index.parent()):
                self.tree.setCurrentIndex(index)
            menu.exec(self.tree.viewport().mapToGlobal(position))
            menu.deleteLater()

    def set_sort(self, column, descending=False, sort_type=None):
        if not self.case or self.busy or not 0 <= column < len(self.case.headers):
            return
        self.view.sorts = []
        widgets = [self.sort_column, self.desc, self.sort_type]
        previous = [w.blockSignals(True) for w in widgets]
        self.sort_column.setCurrentIndex(self.sort_column.findData(column))
        self.desc.setChecked(descending)
        if sort_type is not None:
            self.sort_type.setCurrentIndex(self.sort_type.findData(sort_type))
        for widget, blocked in zip(widgets, previous):
            widget.blockSignals(blocked)
        self.apply()

    def header_sort(self, section):
        if section > 0 and self.case:
            column = section - 1
            descending = not self.view.descending if self.view.sort_column == column else False
            self.set_sort(column, descending)

    def group_column(self, column, append=False, remove=False):
        if not self.case or self.busy or not 0 <= column < len(self.case.headers):
            return
        if remove:
            self.view.groups = [i for i in self.view.groups if i != column]
        elif append:
            if column not in self.view.groups:
                self.view.groups.append(column)
        else:
            self.view.groups = [column]
        self.apply()

    def filter_value(self, column, value, exclude=False):
        if not self.case or self.busy or not 0 <= column < len(self.case.headers):
            return
        if value is None:
            condition = Filter(column, "not_empty" if exclude else "empty")
        else:
            condition = Filter(column, "ne" if exclude else "eq", str(value))
        self.view.filters.append(condition)
        self.apply()

    def more(self):
        if not self.model:
            return
        index = QModelIndex() if self.view.expand_all else self.tree.currentIndex()
        if index.isValid():
            index = index.siblingAtColumn(0)
            if not self.model.node(index).group:
                index = index.parent()
        self.model.fetchMore(index)

    def previous(self):
        if not self.model:
            return
        index = QModelIndex() if self.view.expand_all else self.tree.currentIndex()
        if index.isValid():
            index = index.siblingAtColumn(0)
            if not self.model.node(index).group:
                index = index.parent()
        self.model.previous(index)

    def show_details(self, index, *_):
        if not index.isValid():
            return
        node = self.model.node(index)
        if node.group:
            self.detail_fields = []
            self.details.setPlainText(str(self.model.data(index.siblingAtColumn(0))))
        else:
            text = f"Ligne source : {node.values[0]}\nNote : {node.note or ''}\n\n"
            self.detail_fields = []
            parts, position = [text], len(text.encode('utf-16-le')) // 2
            for column, (header, value) in enumerate(zip(self.case.headers, node.values[1:])):
                block = f"{header}\n{'∅' if value is None else value}\n\n"
                end = position + len(block.encode('utf-16-le')) // 2
                self.detail_fields.append((position,end,column,value))
                parts.append(block)
                position = end
            self.details.setPlainText(''.join(parts))

    def toggle_bookmark(self, index):
        if not self.model or not index.isValid():
            return
        node = self.model.node(index)
        if node.group:
            return
        self.edit_bookmark(node.values[0])

    def edit_bookmark(self, row_id):
        if not self.model or self.busy:
            return
        old = self.model.notes.get(row_id)
        note, ok = QInputDialog.getMultiLineText(self, "Signet / note", "Note (vide = retirer le signet)", old if old is not None else "À examiner")
        if ok:
            case = self.case
            self.run(lambda: case.bookmark(row_id, note or None), lambda _: self.apply(), exclusive=True)

    def annotate_selection(self, mode, note=None):
        if not self.model or self.busy:
            return
        ids = [self.model.node(index).values[0] for index in self.tree.selectionModel().selectedRows()
               if not self.model.node(index).group]
        if not ids:
            self.statusBar().showMessage("Sélectionnez des lignes de données ; les en-têtes de groupes sont ignorés")
            return
        if mode in ("append", "replace") and note is None:
            note, accepted = QInputDialog.getMultiLineText(self, "Note sur la sélection",
                f"{len(ids)} enregistrement(s) · " + ("ajouter à la suite des notes existantes" if mode == "append" else "remplacer les notes existantes"))
            if not accepted:
                return
        case = self.case
        def done(count):
            self.apply()
            self.statusBar().showMessage(f"{count} enregistrement(s) sélectionné(s) traité(s)")
        self.run(lambda: case.bookmark_many(ids, note or "", mode), done, exclusive=True)

    def export_annotations(self):
        if not self.case or self.busy:
            return
        target, _ = QFileDialog.getSaveFileName(self, "Exporter les signets et notes de la vue filtrée", "signets.csv", "CSV (*.csv);;Excel (*.xlsx)")
        if not target:
            return
        if not self.export_destination_is_safe(target):
            return
        view, case = copy.deepcopy(self.view), self.case
        view.bookmarks_only = True
        self.run(lambda: case.export(target, view, include_annotations=True),
                 lambda _: self.statusBar().showMessage(f"Signets et notes exportés : {target}"), exclusive=True)

    def save_view(self):
        if not self.case or self.busy:
            return
        name, ok = QInputDialog.getText(self, "Enregistrer la vue", "Nom (un nom existant sera remplacé)")
        if ok and name.strip():
            case, view = self.case, copy.deepcopy(self.view)
            view.header_state = base64.b64encode(bytes(self.tree.header().saveState())).decode("ascii")
            self.run(lambda: case.save_view(name.strip(), view), lambda _: self.statusBar().showMessage("Vue enregistrée dans l’analyse"))

    def load_view(self):
        if not self.case or self.busy:
            return
        self.run(self.case.views, self.choose_view)

    def choose_view(self, views):
        if not views:
            self.statusBar().showMessage("Aucune vue enregistrée")
            return
        name, ok = QInputDialog.getItem(self, "Charger une vue", "Vue", list(views), 0, False)
        if ok:
            self.set_view(views[name])

    def export_csv(self):
        if not self.case or self.busy:
            return
        target, _ = QFileDialog.getSaveFileName(self, "Exporter les résultats filtrés", "resultats.csv", "CSV (*.csv);;Excel (*.xlsx)")
        if not target:
            return
        if not self.export_destination_is_safe(target):
            return
        columns = self.visible_columns()
        if not columns:
            self.error("Choisissez au moins une colonne visible à exporter")
            return
        grouped = False
        if self.view.groups:
            choice, ok = QInputDialog.getItem(self, "Export", "Contenu", ["Lignes filtrées", "Comptages par groupe"], 0, False)
            if not ok:
                return
            grouped = choice == "Comptages par groupe"
        case, view = self.case, copy.deepcopy(self.view)
        self.statusBar().showMessage("Export en cours…")
        self.run(lambda: case.export(target, view, grouped, columns=columns), lambda _: self.statusBar().showMessage(f"Export terminé : {target}"), exclusive=True)

    def export_destination_is_safe(self, target):
        protected = {Path(s.path).resolve() for s in self.documents} | {Path(s.source_info["path"]).resolve() for s in self.documents}
        protected.add(self.rule_store.path.resolve())
        from fireblade.core.paths import protected_destination
        if protected_destination(target,protected):
            self.error("L’export ne peut pas écraser une source, une analyse ouverte ou les règles globales.")
            return False
        return True

    def integrity(self):
        if self.case and self.case.info:
            info = self.case.info
            QMessageBox.information(self, "Provenance de l’import", f"Source : {info['path']}\nOctets : {info['size']}\nLignes : {info['rows']}\nSHA-256 à l’import :\n{info['sha256']}\n\nLa source est lue sans modification. L’identifiant de ligne correspond à l’ordre des enregistrements CSV, hors en-tête (un enregistrement peut occuper plusieurs lignes physiques).")

    def edit_filters(self):
        if not self.case or self.busy:
            return
        children = copy.deepcopy(self.view.filters)
        if self.view.expression is not None:
            children.append(copy.deepcopy(self.view.expression))
        dialog = FilterDialog(self.case.headers, FilterGroup("and", children), self)
        accepted = dialog.exec()
        dialog.deleteLater()
        if accepted:
            expression = dialog.expression
            try:
                # Check casts and regular expressions on a single bound query.
                self.case.condition(expression)
            except ValueError as exc:
                self.error(exc)
                return
            self.view.filters = []
            self.view.expression = expression if expression.children else None
            self.apply()

    def edit_sort(self):
        if not self.case or self.busy:
            return
        keys = self.view.sorts or ([SortKey(self.view.sort_column, self.view.sort_type, self.view.descending)] if self.view.sort_column is not None else [])
        dialog = SortDialog(self.case.headers, keys, self)
        accepted = dialog.exec()
        dialog.deleteLater()
        if accepted:
            view = copy.deepcopy(self.view)
            view.sorts = dialog.keys
            first = dialog.keys[0] if dialog.keys else None
            view.sort_column = first.column if first else None
            view.sort_type = first.kind if first else "text"
            view.descending = first.descending if first else False
            self.set_view(view)

    def edit_rules(self):
        if not self.case or self.busy:
            return
        dialog = RulesDialog(self.case.headers, self.view.format_rules, self)
        accepted = dialog.exec()
        dialog.deleteLater()
        if accepted:
            self.view.format_rules = dialog.rules
            self.apply()

    def apply_profile(self):
        if not self.case or self.busy:
            return
        profile = detect_profile(self.case.headers)
        if profile is None:
            self.statusBar().showMessage("Aucun profil reconnu : affichage CSV générique conservé")
            return
        from fireblade.core.profiles import profile_transformations
        def finish():
            view, order = profile_view(profile, self.case.headers)
            self.set_view(view)
            header = self.tree.header()
            for position,column in enumerate(order,1):
                header.moveSection(header.visualIndex(column+1),position)
                self.tree.setColumnHidden(column+1,False)
            self.statusBar().showMessage(f'Profil {profile.name} appliqué ; valeurs sources intactes, conversions dans des colonnes dérivées')
        definitions = profile_transformations(profile,self.case.headers)
        if definitions:
            from fireblade.ui.derived_columns import add_columns
            add_columns(self,definitions,finish)
        else:
            finish()

    def cell_details(self):
        if not self.model or self.busy:
            return
        index = self.tree.currentIndex()
        if not index.isValid() or self.model.node(index).group or index.column() == 0:
            self.statusBar().showMessage("Sélectionnez une cellule de données")
            return
        raw = self.model.node(index).values[index.column()]
        raw = "" if raw is None else str(raw)
        dialog = QDialog(self)
        dialog.setWindowTitle(self.case.headers[index.column() - 1])
        dialog.resize(800, 520)
        layout = QVBoxLayout(dialog)
        mode = QComboBox()
        mode.addItems(["Texte brut", "JSON formaté", "XML formaté"])
        layout.addWidget(mode)
        text = QPlainTextEdit(raw)
        text.setReadOnly(True)
        layout.addWidget(text)
        message = QLabel()
        layout.addWidget(message)
        def render():
            try:
                if mode.currentIndex() and len(raw) > 2 * 1024 * 1024:
                    raise ValueError("Formatage limité à 2 Mo pour préserver la réactivité ; texte brut disponible")
                if mode.currentIndex() == 2:
                    if "<!DOCTYPE" in raw.upper() or "<!ENTITY" in raw.upper():
                        raise ValueError("Les déclarations DTD et entités ne sont pas prises en charge")
                    from xml.dom.minidom import parseString
                    document = parseString(raw)
                    try:
                        value = document.toprettyxml(indent="  ")
                    finally:
                        document.unlink()
                else:
                    value = json.dumps(json.loads(raw), ensure_ascii=False, indent=2) if mode.currentIndex() else raw
                text.setPlainText(value)
                message.clear()
            except (ValueError, RecursionError, ExpatError) as exc:
                text.setPlainText(raw)
                message.setText(f"Cellule non formatable : {exc}")
        mode.currentIndexChanged.connect(render)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()
        dialog.deleteLater()

    def highlight(self):
        if not self.case or self.busy:
            return
        value, ok = QInputDialog.getText(self, "Coloration conditionnelle", "Colorer les lignes contenant ce texte (vide = désactiver)", text=self.view.highlight)
        if ok:
            self.view.highlight = value
            self.apply()

    def copy_rows(self):
        if not self.model or self.busy:
            return
        import csv
        import io
        out = io.StringIO(newline="")
        writer = csv.writer(out, delimiter="\t")
        columns = self.visible_columns()
        if self.preferences.copy_headers:
            writer.writerow([self.case.headers[i] for i in columns])
        for index in self.tree.selectionModel().selectedRows():
            node = self.model.node(index)
            if not node.group:
                writer.writerow([node.values[i + 1] for i in columns])
        QApplication.clipboard().setText(out.getvalue())

    def closeEvent(self, event):
        if self.busy or self.pool.activeThreadCount():
            self.statusBar().showMessage("Interrompez ou attendez la fin de l’opération avant de fermer.")
            event.ignore()
            return
        self.detach()
        event.accept()


def main():
    parser = argparse.ArgumentParser(description="Explorateur local de CSV forensic")
    parser.add_argument("--config", type=Path, help="Fichier de configuration TOML")
    parser.add_argument("file", nargs="?", type=Path, help="CSV ou analyse à ouvrir")
    parser.add_argument("--self-test-report", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--appearance-report", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--stress-spec", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--stress-report", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    config = args.config if args.config is not None else default_config()
    try:
        settings = load_settings(config)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    app = QApplication(sys.argv)
    app.setApplicationName("Fireblade")
    apply_theme(app)
    if args.appearance_report is not None:
        from fireblade.validation.appearance import run_appearance
        raise SystemExit(run_appearance(app,args.appearance_report))
    if args.stress_report is not None:
        if args.stress_spec is None:parser.error("--stress-spec is required")
        from fireblade.validation.stress import run_stress
        raise SystemExit(run_stress(app,args.stress_spec,args.stress_report))
    if args.self_test_report is not None:
        from fireblade.validation.windows_check import run_check
        raise SystemExit(run_check(app, args.self_test_report))
    window = Window(settings)
    window.show()
    if args.file is not None:
        QTimer.singleShot(0, lambda: window.open_path(args.file))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
