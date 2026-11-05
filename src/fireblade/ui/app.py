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
    QDialogButtonBox, QDockWidget, QFormLayout, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QSplitter, QStackedWidget, QStyle, QToolButton,
    QTreeView, QVBoxLayout, QWidget)

from fireblade.ui.menus import cell_menu, header_menu
from fireblade.core.models import Filter, FilterGroup, SortKey, View, OPERATORS
from fireblade.ui.advanced_dialogs import FilterDialog, RulesDialog, SortDialog
from fireblade.ui.grouping import GroupBar, GroupHeader
from fireblade.core.profiles import detect_profile, profile_view
from fireblade.ui.workspace import WorkspaceMixin
from fireblade.ui.shared_rules import SharedRulesMixin
from fireblade.ui.grid import GridDelegate, GridModel
from fireblade.core.settings import Settings, load_settings
from fireblade.ui.theme import apply_theme
from fireblade.ui.workers import Job
from fireblade.ui.exploration import ExplorationMixin
from fireblade.ui.pinned_grid import PinnedTree
from fireblade.runtime.resources import default_config
from fireblade.ui.help_dialogs import show_about, show_guide, show_licenses, show_tutorial, show_investigation_guide, show_ioc_guide, show_coverage_guide


from fireblade.ui.collection import CollectionMixin
from fireblade.ui.investigations import InvestigationMixin
from fireblade.ui.investigation_tools import InvestigationToolsMixin
from fireblade.ui.timeline import TimelineMixin


from fireblade.ui.file_commands import FileCommandsMixin
from fireblade.ui.export_commands import ExportCommandsMixin


from fireblade.ui.start_workflow import StartWorkflowMixin


class Window(StartWorkflowMixin, FileCommandsMixin, ExportCommandsMixin, TimelineMixin, InvestigationToolsMixin, InvestigationMixin, CollectionMixin, ExplorationMixin, SharedRulesMixin, WorkspaceMixin, QMainWindow):
    """Desktop workspace. Case-free mode is an opt-out for component qualification."""
    def __init__(self, settings=None, rule_path=None, investigation_root=None, require_case=True):
        super().__init__()
        self.settings = settings or Settings()
        self._investigation_root = investigation_root
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
        self._workspace_epoch = 0
        self.build_ui()
        self.setup_workspace()
        self.setup_shared_rules(rule_path)
        self.setup_exploration()
        self.setup_collection()
        self.setup_investigations()
        self.setup_investigation_tools()
        self.setup_timeline()
        from fireblade.ui.ioc_hunt import HuntPanel
        self.ioc_panel = HuntPanel(self)
        self.workbench.addTab(self.ioc_panel, "Chasse IOC")
        from fireblade.ui.coverage import CoveragePanel
        self.coverage_panel=CoveragePanel(self)
        self.coverage_dialog=QDialog(self)
        self.coverage_dialog.setWindowTitle('Vérification des imports et diagnostics')
        self.coverage_dialog.resize(950, 650)
        QVBoxLayout(self.coverage_dialog).addWidget(self.coverage_panel)
        self.setup_start_workflow(require_case)
        from fireblade.ui.command_layout import organize_commands
        organize_commands(self)
        from fireblade.ui.modular_workspace import WorkspaceLayout
        self.workspace_layout = WorkspaceLayout(self)
        self.setAcceptDrops(True)
        from fireblade.ui.language import apply_language
        apply_language(self)
        self._ui_ready = True

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
        compatibility = file_menu.addMenu("Compatibilité Timeline Explorer")
        action(compatibility, "Importer avec un plugin TLE (.NET)…", self.import_with_tle_plugin, requires_file=False)
        action(file_menu, "Ouvrir une analyse…", self.open_case, "Ctrl+Shift+O", False)
        action(compatibility, 'Importer les préférences Timeline Explorer…', self.import_tle_settings,requires_file=False)
        action(compatibility, "Importer une session Timeline Explorer…", lambda: self.import_tle_session(), requires_file=False)
        action(file_menu, "Ouvrir une session…", lambda: self.load_session(), requires_file=False)
        action(file_menu, "Enregistrer la session…", lambda: self.save_session(), "Ctrl+Shift+S")
        action(compatibility, "Exporter une session TLE (sources et signets)…", lambda: self.export_tle_session())
        action(file_menu, "Fermer l’onglet", lambda: self.close_document(self.active_document), "Ctrl+W")
        action(file_menu, "Vider la file d’ouverture", self.clear_open_queue, requires_file=False)
        action(file_menu, "Rouvrir le dernier onglet fermé", self.reopen_closed, "Ctrl+Shift+T", False)
        file_menu.addSeparator()
        export = action(file_menu, "Exporter…", self.export_csv, "Ctrl+Shift+E", icon=QStyle.SP_DialogSaveButton)
        action(file_menu, "Exporter les signets et notes…", self.export_annotations)
        file_menu.addSeparator()
        action(file_menu, "Quitter", self.close, "Alt+F4", False)
        action(edit_menu, "Copier les lignes", self.copy_rows, "Ctrl+C")
        action(edit_menu, "Signet / note…", lambda: self.toggle_bookmark(self.tree.currentIndex()))
        action(edit_menu, "Marquer la sélection", lambda: self.annotate_selection("mark"), "Ctrl+Alt+B")
        action(edit_menu, "Ajouter une note à la sélection…", lambda: self.annotate_selection("append"))
        action(edit_menu, "Remplacer les notes de la sélection…", lambda: self.annotate_selection("replace"))
        action(edit_menu, "Retirer les signets de la sélection", lambda: self.annotate_selection("remove"), "Ctrl+Shift+M")
        grouping = action(view_menu, "Regrouper…", self.group_by)
        action(view_menu, "Palette de commandes…", self.command_palette, "Ctrl+Shift+K", False)
        action(view_menu, "Colonnes…", self.columns)
        action(view_menu, "Hauteur des lignes…", self.edit_row_heights)
        action(view_menu, "Réinitialiser les largeurs", self.reset_widths, "Ctrl+R")
        action(view_menu, "Résumés et tri des groupes…", self.edit_groups)
        action(view_menu, "Déplier tous les groupes (vue paginée)", self.expand_groups, "Ctrl+M")
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
        expert_view=view_menu.addMenu('Profils et compatibilité')
        action(expert_view, "Profils et plugins…", self.manage_plugins, requires_file=False)
        action(expert_view, "Légende des supertimelines…", self.show_legend, requires_file=False)
        action(view_menu, "Tri sur plusieurs colonnes…", self.edit_sort)
        action(filter_menu, "Expression textuelle…", self.edit_filter_text)
        action(filter_menu, "Éditeur ET / OU / NON…", self.edit_filters, "Ctrl+Alt+F")
        action(filter_menu, "Filtrer sur la cellule active", self.filter_current_cell, "Ctrl+Shift+F")
        add_filter = action(filter_menu, "Ajouter un filtre…", self.add_filter)
        action(filter_menu, "Effacer les filtres", self.clear_filters, "Ctrl+E")
        action(view_menu, "Réinitialiser la vue", self.reset)
        action(filter_menu, "Rechercher dans toutes les analyses…", self.find_workspace, "Ctrl+F")
        action(analysis_menu, "Enregistrer la vue…", self.save_view, "Ctrl+S")
        action(analysis_menu, "Charger une vue…", self.load_view, "Ctrl+L")
        layouts_menu=analysis_menu.addMenu('Dispositions de la grille')
        action(layouts_menu, "Exporter la disposition…", self.export_layout)
        action(layouts_menu, "Importer une disposition…", self.import_layout)
        analysis_menu.addSeparator()
        action(analysis_menu, "Règles de coloration…", self.edit_rules)
        functions_menu=analysis_menu.addMenu('Calculs et conversions')
        action(functions_menu, "Charger des fonctions .NET…", self.load_dotnet_functions)
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
        action(functions_menu, 'Convertir une date…', lambda: edit_derived(self))
        action(functions_menu, 'Ajouter une colonne calculée…', lambda: edit_derived(self,expression=True))
        action(functions_menu, 'Contrôler les colonnes dérivées…', lambda: quality(self))
        self.cancel_action = action(analysis_menu, "Interrompre la requête", self.interrupt_queries, requires_file=False)
        self.cancel_action.setEnabled(False)
        action(help_menu, "Tutoriel complet — toutes les fonctionnalités", lambda: show_tutorial(self), requires_file=False)
        action(help_menu, "Couverture de collecte et diagnostics", lambda: show_coverage_guide(self), requires_file=False)
        action(help_menu, "Chasse IOC en masse", lambda: show_ioc_guide(self), requires_file=False)
        action(help_menu, "Chronologie, sauvegardes et rapports", lambda: show_investigation_guide(self), requires_file=False)
        action(help_menu, "Guide d’utilisation", lambda: show_guide(self), "F1", False)
        action(help_menu, "Licences", lambda: show_licenses(self), requires_file=False)
        action(help_menu, "À propos de Fireblade", lambda: show_about(self), requires_file=False)

        toolbar = self.main_toolbar = self.addToolBar("Fichier")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        toolbar.addAction(open_csv)
        toolbar.addAction(export)
        # Column filters and the grouping bar already expose these operations.

        self.content_stack = QStackedWidget()
        welcome = QWidget()
        welcome_layout = QVBoxLayout(welcome)
        welcome_layout.addStretch()
        message = self.welcome_title = QLabel("Nouvelle analyse")
        message.setAlignment(Qt.AlignCenter)
        welcome_layout.addWidget(message)
        folder_button = QPushButton('Parser un dossier…')
        folder_button.setToolTip('Artefacts Windows, journaux Linux ou collecte CatScale. Traitement en arrière-plan.')
        folder_button.clicked.connect(self.parse_collection)
        welcome_layout.addWidget(folder_button, 0, Qt.AlignHCenter)
        disk_button = QPushButton("Analyser un disque…")
        disk_button.clicked.connect(self.choose_disk)
        welcome_layout.addWidget(disk_button, 0, Qt.AlignHCenter)
        open_button = QPushButton("Importer un fichier…")
        open_button.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        open_button.clicked.connect(self.import_csv)
        welcome_layout.addWidget(open_button, 0, Qt.AlignHCenter)
        hint = QLabel("CSV · TSV · TXT · XLS · XLSX")
        hint.setAlignment(Qt.AlignCenter)
        welcome_layout.addWidget(hint)
        welcome_layout.addStretch()
        self.content_stack.addWidget(welcome)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self.analysis_add_bar = QWidget()
        add_layout = QHBoxLayout(self.analysis_add_bar)
        add_layout.setContentsMargins(0, 0, 0, 0)
        add_layout.addWidget(QLabel('Importer :'))
        layout.addWidget(self.analysis_add_bar)
        self.source = QLabel()
        self.source.setMaximumWidth(240)
        self.statusBar().addPermanentWidget(self.source)
        self.rules_summary = QLabel()
        self.rules_summary.setMaximumWidth(180)
        self.statusBar().addPermanentWidget(self.rules_summary)
        row = QHBoxLayout()
        row.addWidget(QLabel("Rechercher :"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Texte, IP, chemin, empreinte… · Entrée pour rechercher")
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(self.search_workspace_or_active)
        self.search_scope = QComboBox()
        self.search_scope.addItem('Tous les artefacts', 'all')
        self.search_scope.addItem('Artefact actif', 'active')
        row.addWidget(self.search_scope)
        row.addWidget(self.search, 1)
        clear = QPushButton("Effacer les filtres")
        clear.setToolTip("Retirer les recherches et filtres sans modifier les groupes, le tri ou les couleurs.")
        clear.clicked.connect(self.clear_filters)
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
        details_button = QToolButton()
        details_button.setDefaultAction(self.details_action)
        group_row.addWidget(details_button)
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
        self.tree.header().setToolTip("Glissez les en-têtes pour réordonner ; clic droit pour les options. Ordre et largeurs mémorisés par artefact.")
        self.tree.header().setFirstSectionMovable(False)
        self.tree.header().setMinimumHeight(max(26, self.fontMetrics().height() + 8))
        self.tree.doubleClicked.connect(self.toggle_bookmark)
        self.tree.expanded.connect(lambda index: self.model.fetchMore(index) if self.model and not self.model.node(index).children else None)
        self.tree.collapsed.connect(lambda index: self.model.unload(index) if self.model else None)
        self.tree.header().sectionClicked.connect(self.header_sort)
        for grid in (self.tree, *self.tree.frozen_views):
            grid.header().filterChanged.connect(self.column_search)
            grid.header().sortRequested.connect(self.set_sort)
            if grid is not self.tree:
                grid.header().sectionClicked.connect(self.header_sort)
        self.tree.header().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.header().customContextMenuRequested.connect(self.show_header_menu)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_cell_menu)
        self.tree.setToolTip("Clic dans la première colonne : surligner la ligne / signet. Double-clic sur une donnée : modifier la note.")
        splitter.addWidget(self.tree)
        from fireblade.ui.layout_styles import AppearanceTextEdit
        self.details = AppearanceTextEdit()
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
        if hasattr(self, 'save_case_action'):
            self.save_case_action.setEnabled(self.active_investigation is not None and not self.busy)
        if hasattr(self, 'update_collection_controls'):
            self.update_collection_controls()

    def coverage_notice(self,stage,severity,reason,path='',**metrics):
        panel=getattr(self,'coverage_panel',None)
        if panel:panel.record(stage,severity,str(reason),path,**metrics)

    def error(self, message):
        panel=getattr(self,'coverage_panel',None)
        if panel and (not panel.events or panel.events[-1]['reason']!=str(message)):
            self.coverage_notice('Analyse','error',message,str(self.case.path) if self.case else '')
        self.statusBar().showMessage("Opération interrompue ou en erreur")
        QMessageBox.warning(self, "Opération impossible", str(message))

    def interrupt_queries(self):
        if getattr(self,'investigation_task',None):self.investigation_task.interrupt()
        if getattr(self,'timeline_panel',None):self.timeline_panel.interrupt()
        if getattr(self,'ioc_panel',None):self.ioc_panel.interrupt()
        if getattr(self,'coverage_panel',None):self.coverage_panel.interrupt()
        if getattr(self, 'collection', None) is not None:
            self.collection.interrupt()
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

    def run(self, fn, done, exclusive=False, on_cancel=None, on_error=None, coverage_stage=None, coverage_context=None):
        if exclusive and self.busy:
            return
        if exclusive:
            self.busy = True
            self.centralWidget().setEnabled(False)
            for dock in self.findChildren(QDockWidget):dock.setEnabled(False)
            self.set_file_actions(False)
            self.cancel_action.setEnabled(True)
        coverage_path=coverage_context or (str(self.case.path) if self.case else "")
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
                for dock in self.findChildren(QDockWidget):dock.setEnabled(True)
                self.set_file_actions(self.model is not None)
            return True

        def finish(value):
            if not release():return
            done(value)

        def fail(message):
            if not release():return
            self.coverage_notice(coverage_stage or "Analyse","error",message,coverage_path)
            if on_error:
                on_error(message)
            else:
                self.error(message)

        def was_cancelled():
            if not release():return
            if coverage_stage:self.coverage_notice(coverage_stage,"warning","Opération interrompue ; aucun succès complet attesté.",coverage_path)
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
        def finish_when_idle():
            # A queued done signal can arrive before QRunnable.run has returned.
            # Keep processing events until ownership really leaves the pool;
            # otherwise an immediate reopen is rejected by can_open_file().
            if self.pool.activeThreadCount():
                QTimer.singleShot(1,finish_when_idle)
            else:
                loop.quit()
        def done(value):
            result.append(value)
            finish_when_idle()
        def failed(error):
            errors.append(error)
            finish_when_idle()
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
            blocked=previous_busy or getattr(self,'_collection_open_pending',False) or getattr(self,'_investigation_switching',False)
            self.centralWidget().setEnabled(not blocked)
            self.set_file_actions(self.model is not None and not blocked)
            loop.deleteLater()
        if errors:
            raise RuntimeError(errors[0])
        return result[0]

    def can_open_file(self, allow_without_case=False):
        if not allow_without_case and not self.require_active_case():
            return False
        if getattr(self,'_collection_open_pending',False):
            self.statusBar().showMessage('Ouverture des résultats de la collecte…')
            return False
        if getattr(self,'_investigation_switching',False):
            self.statusBar().showMessage('Changement de case en cours…')
            return False
        if self.busy or self.pool.activeThreadCount() or self.jobs or (self.model and self.model.jobs):
            self.statusBar().showMessage("Attendez ou interrompez la requête avant de changer d’analyse.")
            return False
        return True













    def detach(self):
        self._workspace_epoch += 1
        self.save_format_layout()
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
        self.update_alert_context_bar()



    def attach(self, case, initial_view=None, header_state=None, auto_layout=None):
        if hasattr(self,'workbench'):self.workbench.setCurrentIndex(0)
        initial_view, auto_layout = self.prepare_context_view(case, initial_view, auto_layout)
        use_auto_layout=(initial_view is None or header_state == b'') if auto_layout is None else auto_layout
        collection = getattr(self, 'collection', None)
        if auto_layout is None and collection is not None and collection.report.get('organization', 'files') != 'files':
            if any(document['path'] == str(case.path) for document in collection.report['documents']):
                # The organization selected at import owns the initial/saved view.
                use_auto_layout = False
        self._layout_save_enabled=True
        self.case = case
        self.content_stack.setCurrentIndex(1)
        self.set_file_actions(True)
        self.cancel_action.setEnabled(True)
        self.model = GridModel(case, self.pool, self)
        self.model.date_format = self.preferences.date_format
        self.model.date_pattern = self.preferences.custom_date_format
        self.model.dark = self.preferences.theme == "dark"
        self.model.bookmark_requested.connect(self.mark_row)
        self.model.memory_evicted.connect(self.tree.collapse)
        for panel in self.tree.frozen_views:
            self.model.memory_evicted.connect(panel.collapse)
        self.model.status.connect(self.statusBar().showMessage)
        self.model.error.connect(self.error)
        self.tree.setModel(self.model)
        self.tree.selectionModel().currentChanged.connect(self.show_details)
        self.tree.header().setSectionsMovable(True)
        self.tree.header().setSectionResizeMode(QHeaderView.Interactive)
        for i in range(self.model.columnCount()):
            self.tree.setColumnHidden(i, False)
            self.tree.header().moveSection(self.tree.header().visualIndex(i), i)
            self.tree.setColumnWidth(i, 90 if i == 0 else 150)
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
            from fireblade.core.preferences import default_pinned_columns
            initial_view=View(pinned_columns=default_pinned_columns(self.preferences,case.headers,case.info))
        self.set_view(initial_view)
        if header_state is not None:
            self.tree.header().restoreState(header_state)
        self.restore_pins()
        if use_auto_layout:
            self.restore_format_layout()
        self.track_case()
        if not header_state:self.configure_context_columns()
        self.update_alert_context_bar()
        if hasattr(self,'active_investigation'):
            self.remember_investigation_collection()
            self.update_investigation_badge()

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
        self.groups_label.set_groups(self.case.headers, self.view.groups)
        for grid in (self.tree, *self.tree.frozen_views):
            grid.header().sync_filters(self.view.filters, self.view.sort_column, self.view.descending)
        section = self.view.sort_column
        self.tree.header().setSortIndicatorShown(section is not None)
        if section is not None:
            self.tree.header().setSortIndicator(section + 1, Qt.DescendingOrder if self.view.descending else Qt.AscendingOrder)
        self.global_rules_action.blockSignals(True)
        self.global_rules_action.setChecked(self.view.global_rules_enabled)
        self.global_rules_action.blockSignals(False)
        self._expand_generation += 1
        from fireblade.ui.layout_styles import apply_panel_styles
        apply_panel_styles(self)
        self.model.reset(self.view, self.global_rules_for_view())
        self.detail_fields = []
        self.details.clear()
        self.count_generation += 1
        generation = self.count_generation
        view = copy.deepcopy(self.view)
        case = self.case
        self.count_label.setText("Comptage…")
        # Obsolete queued counts need not scan a large case before the latest view.
        def footer_values():
            if generation!=self.count_generation:return None
            return case.total_summary(view) if view.show_total_footer and view.total_summaries else (case.count(view),)
        def show_footer(values):
            if generation!=self.count_generation or values is None:return
            label=f"{values[0]:,} / {case.info['rows']:,} lignes"
            if len(values)>1:
                label+=' · '+' · '.join(f"{summary.operation}({case.headers[summary.column][:256]})={'∅' if value is None else str(value)[:600]}" for summary,value in zip(view.total_summaries,values[1:]))
            self.count_label.setText(label)
            panel=getattr(self,"coverage_panel",None)
            if panel:panel.stale=True;panel.update_badge()
        self.run(footer_values,show_footer,
                 on_cancel=lambda: self.count_label.setText("Comptage interrompu") if generation == self.count_generation else None)

    def reset(self):
        self.tree.set_pins([])
        self.set_view(View())

    def set_view(self, view):
        for grid in (self.tree, *self.tree.frozen_views):
            grid.header().timer.stop()
            grid.header().pending.clear()
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
        from fireblade.ui.column_manager import ColumnManager
        header = self.tree.header()
        sections = [header.logicalIndex(position) for position in range(header.count()) if header.logicalIndex(position) > 0]
        order = [section - 1 for section in sections]
        state = dict(order=order,
                     hidden=[column for column in order if self.tree.isColumnHidden(column + 1)],
                     left=list(self.view.pinned_columns), right=list(self.view.right_pinned_columns),
                     widths={column: self.tree.columnWidth(column + 1) for column in order})
        dialog = ColumnManager(self.case.headers, state, self)
        try:
            if dialog.exec() != QDialog.Accepted:
                return
            result = dialog.state()
        finally:
            dialog.deleteLater()
        # Move from the last slot backwards: placing a section that is already
        # correct would otherwise push the earlier ones out of place.
        for position in range(len(result['order']), 0, -1):
            section = result['order'][position - 1] + 1
            if section >= header.count():
                continue
            if header.visualIndex(section) != position:
                header.moveSection(header.visualIndex(section), position)
        self.view.pinned_columns = result['left']
        self.view.right_pinned_columns = result['right']
        self.restore_pins()
        for column in range(len(self.case.headers)):
            section = column + 1
            hidden = column in result['hidden']
            self.tree.setColumnHidden(section, hidden)
            if hidden:
                continue
            width = result['widths'].get(column)
            if width is None:
                continue
            if column in result['left'] + result['right']:
                self.view.pinned_widths[str(column)] = width
            else:
                self.tree.setColumnWidth(section, width)
        self.capture_pin_widths()
        self.save_format_layout()

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

    def column_search(self, column, text):
        if not self.case or not 0 <= column < len(self.case.headers):
            return
        if self.busy:
            # Keep the edit pending while an import or query owns the interface.
            self.tree.header().queue_filter(column, text)
            return
        existing = next((f for f in self.view.filters if f.column == column and f.operator == "contains"), None)
        if existing is not None:
            self.view.filters.remove(existing)
        if text:
            self.view.filters.append(Filter(column, "contains", text))
        self.apply()

    def header_sort(self, section):
        if section > 0 and self.case:
            column = section - 1
            descending = not self.view.descending if self.view.sort_column == column else False
            self.set_sort(column, descending)

    def group_column(self, column, append=False, remove=False, clear=False, position=None):
        if not self.case or self.busy:
            return
        if clear:
            self.view.groups = []
            self.apply()
            return
        if not 0 <= column < len(self.case.headers):
            return
        if remove:
            self.view.groups = [i for i in self.view.groups if i != column]
        elif append:
            # Dropping an existing level moves it; dropping a new one inserts it
            # where the analyst released it.
            if column in self.view.groups:
                self.view.groups.remove(column)
            if position is None or not 0 <= position <= len(self.view.groups):
                self.view.groups.append(column)
            else:
                self.view.groups.insert(position, column)
        else:
            self.view.groups = [column]
        self.apply()

    def filter_current_cell(self):
        """Use the stored value, not a formatted/truncated display string."""
        if not self.model or self.busy:
            return
        index = self.tree.currentIndex()
        if not index.isValid() or index.column() == 0:
            return
        node = self.model.node(index)
        if not node.group:
            self.filter_value(index.column() - 1, node.values[index.column()])

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
        self.update_alert_context_bar()
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
        if node.group or node.footer or index.column() == 0:
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


    def save_view(self):
        if not self.case or self.busy:
            return
        name, ok = QInputDialog.getText(self, "Enregistrer la vue", "Nom (un nom existant sera remplacé)")
        if ok and name.strip():
            self.capture_pin_widths()
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
            view=copy.deepcopy(self.view);view.format_rules=dialog.rules
            self.set_view(view)

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

    def command_palette(self):
        """Every menu command behind one field, for actions without a visible button."""
        from fireblade.ui.command_palette import CommandPalette
        dialog = CommandPalette(self)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

    def highlight(self):
        if not self.case or self.busy:
            return
        value, ok = QInputDialog.getText(self, "Coloration conditionnelle", "Surligner les occurrences (vide = désactiver)", text=self.view.highlight)
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
        if getattr(self, "disk_job", None) is not None or self.disk_pool.activeThreadCount() or self._disk_pending or self._folder_queue:
            self.statusBar().showMessage("Arrêtez ou attendez l’indexation du disque avant de fermer.")
            event.ignore()
            return
        if self.busy or self.pool.activeThreadCount() or getattr(self,'_collection_open_pending',False) or getattr(self,'_investigation_switching',False):
            self.statusBar().showMessage("Interrompez ou attendez la fin de l’opération avant de fermer.")
            event.ignore()
            return
        if getattr(self,'active_investigation',None) is not None:
            if self.open_queue:
                self.statusBar().showMessage('Terminez ou videz la file d’ouverture avant de fermer le case.')
                event.ignore()
                return
            if not self.persist_investigation():
                event.ignore()
                return
        self._closing_workspace = True
        self.detach()
        if getattr(self,'timeline_panel',None):self.timeline_panel.reset_workspace()
        if getattr(self,'ioc_panel',None):self.ioc_panel.reset_workspace()
        if getattr(self,'coverage_panel',None):self.coverage_panel.reset_workspace()
        if hasattr(self,'active_investigation'):
            self.clear_context_preview()
            self.release_investigation_lease()
            self.active_investigation=None
        self.workspace_layout.save()
        event.accept()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'navigator'):self.update_navigation_visibility()


def main():
    parser = argparse.ArgumentParser(description="Explorateur local de CSV forensic")
    parser.add_argument("--config", type=Path, help="Fichier de configuration TOML")
    parser.add_argument("file", nargs="?", type=Path, help="CSV ou analyse à ouvrir")
    parser.add_argument("--self-test-report", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--appearance-report", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--workspace-report", type=Path, help=argparse.SUPPRESS)
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
    if args.workspace_report is not None:
        from fireblade.validation.workspace import run_workspace
        raise SystemExit(run_workspace(app,args.workspace_report))
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
    from fireblade.core.preferences import load_preferences
    try:
        animate = load_preferences().startup_animation
    except (OSError, ValueError, TypeError):
        animate = True
    splash = None
    if animate:
        from fireblade.ui.startup import StartupAnimation
        splash = StartupAnimation()
        splash.show()
        app.processEvents()
    window = Window(settings, require_case=True)
    window._startup_file = args.file
    if splash is not None:
        splash.finished.connect(window.show)
        splash.finished.connect(splash.close)
        splash.animation.start()
    else:
        window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
