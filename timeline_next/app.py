from __future__ import annotations

import copy
import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QModelIndex, QThreadPool, QTimer, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QSplitter, QStackedWidget, QStyle,
    QTreeView, QVBoxLayout, QWidget)

from .dialogs import ImportDialog
from .engine import Case
from .menus import cell_menu, header_menu
from .models import AnalysisSnapshot, Filter, View, OPERATORS
from .grid import GridModel
from .settings import Settings, load_settings
from .theme import apply_theme
from .workers import Job, Signals


class Window(QMainWindow):
    def __init__(self, settings=None):
        super().__init__()
        self.settings = settings or Settings()
        self.setWindowTitle("Timeline Next")
        self.resize(1280, 800)
        self.case, self.model = None, None
        self.view = View()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.jobs = set()
        self.busy = False
        self.count_generation = 0
        self.build_ui()
        self.setAcceptDrops(True)

    def build_ui(self):
        file_menu = self.menuBar().addMenu("&Fichier")
        edit_menu = self.menuBar().addMenu("&Édition")
        view_menu = self.menuBar().addMenu("&Affichage")
        filter_menu = self.menuBar().addMenu("Fi&ltres")
        analysis_menu = self.menuBar().addMenu("A&nalyse")
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

        open_csv = action(file_menu, "Ouvrir un CSV…", self.import_csv, "Ctrl+O", False, QStyle.SP_DialogOpenButton)
        action(file_menu, "Ouvrir une analyse…", self.open_case, "Ctrl+Shift+O", False)
        file_menu.addSeparator()
        export = action(file_menu, "Exporter…", self.export_csv, "Ctrl+E", icon=QStyle.SP_DialogSaveButton)
        file_menu.addSeparator()
        action(file_menu, "Quitter", self.close, "Alt+F4", False)
        action(edit_menu, "Copier les lignes", self.copy_rows, "Ctrl+C")
        action(edit_menu, "Signet / note…", lambda: self.toggle_bookmark(self.tree.currentIndex()))
        grouping = action(view_menu, "Regrouper…", self.group_by)
        action(view_menu, "Colonnes…", self.columns)
        view_menu.addSeparator()
        self.sort_action = action(view_menu, "Options de tri", lambda checked: self.sort_options.setVisible(checked), requires_file=False)
        self.sort_action.setCheckable(True)
        self.details_action = action(view_menu, "Détails de la ligne", lambda checked: self.details.setVisible(checked), requires_file=False)
        self.details_action.setCheckable(True)
        self.details_action.setChecked(True)
        add_filter = action(filter_menu, "Ajouter un filtre…", self.add_filter)
        action(filter_menu, "Réinitialiser", self.reset)
        action(analysis_menu, "Enregistrer la vue…", self.save_view, "Ctrl+S")
        action(analysis_menu, "Charger une vue…", self.load_view, "Ctrl+L")
        analysis_menu.addSeparator()
        action(analysis_menu, "Coloration des lignes…", self.highlight)
        action(analysis_menu, "Provenance et SHA-256…", self.integrity)
        analysis_menu.addSeparator()
        self.cancel_action = action(analysis_menu, "Interrompre la requête", self.interrupt_queries, requires_file=False)
        self.cancel_action.setEnabled(False)

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
        self.groups_label = QLabel("Groupement : aucun")
        group_row.addWidget(self.groups_label, 1)
        change_groups = QPushButton("Regrouper…")
        change_groups.clicked.connect(self.group_by)
        group_row.addWidget(change_groups)
        layout.addLayout(group_row)
        splitter = QSplitter(Qt.Vertical)
        self.tree = QTreeView()
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionBehavior(QTreeView.SelectRows)
        self.tree.setSelectionMode(QTreeView.ExtendedSelection)
        self.tree.setHorizontalScrollMode(QTreeView.ScrollPerPixel)
        self.tree.setAnimated(False)
        self.tree.setIndentation(16)
        self.tree.header().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.tree.header().setMinimumHeight(24)
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
        def release():
            self.jobs.discard(job)
            job.signals.done.disconnect(finish)
            job.signals.error.disconnect(fail)
            job.signals.cancelled.disconnect(was_cancelled)
            job.signals.progress.disconnect()
            if exclusive:
                self.busy = False
                self.centralWidget().setEnabled(True)
                self.set_file_actions(self.model is not None)

        def finish(value):
            release()
            done(value)

        def fail(message):
            release()
            if on_error:
                on_error(message)
            else:
                self.error(message)

        def was_cancelled():
            release()
            self.statusBar().showMessage("Opération annulée.")
            if on_cancel:
                on_cancel()

        job.signals.done.connect(finish)
        job.signals.error.connect(fail)
        job.signals.cancelled.connect(was_cancelled)
        job.signals.progress.connect(self.statusBar().showMessage)
        self.pool.start(job)
        return job

    def can_open_file(self):
        if self.busy or self.pool.activeThreadCount() or self.jobs or (self.model and self.model.jobs):
            self.statusBar().showMessage("Attendez ou interrompez la requête avant de changer d’analyse.")
            return False
        return True

    def import_csv(self):
        if not self.can_open_file():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir un CSV", "", "CSV / TSV (*.csv *.tsv *.txt);;Tous les fichiers (*)")
        if path:
            self.import_file(path)

    def import_file(self, path):
        if not self.can_open_file():
            return
        path = Path(path)
        if not path.is_file():
            self.error("Le fichier source est introuvable.")
            return
        dialog = ImportDialog(path, self)
        if not dialog.exec():
            return
        target, delimiter, encoding = dialog.values()
        if target.exists():
            self.error("Choisissez un nouveau nom : une base existante ne sera pas écrasée.")
            return
        try:
            candidate = Case(target, settings=self.settings)
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

        self.run(lambda: candidate.import_csv(path, delimiter, encoding, progress.progress.emit),
                 lambda _: self.attach(candidate), exclusive=True, on_cancel=cancelled, on_error=failed)

    def snapshot_analysis(self):
        if not self.case or not self.model:
            return None
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
            restored = Case(path, settings=self.settings)
            if restored.info != snapshot.source_info:
                raise ValueError("L’analyse précédente a été remplacée par un autre jeu de données.")
            self.attach(restored, initial_view=snapshot.view, header_state=snapshot.header_state)
        except Exception as exc:
            if restored is not None:
                if self.case is restored:
                    self.detach()
                else:
                    restored.close()
            return str(exc) or type(exc).__name__
        return None

    def open_path(self, path):
        path = Path(path)
        if path.suffix.lower() == ".timeline":
            self.load_case(path)
        else:
            self.import_file(path)

    @staticmethod
    def dropped_file(mime):
        urls = mime.urls() if mime.hasUrls() else []
        if len(urls) != 1 or not urls[0].isLocalFile():
            return None
        path = Path(urls[0].toLocalFile())
        if not path.is_file() or path.suffix.lower() not in (".csv", ".tsv", ".txt", ".timeline"):
            return None
        return path

    def dragEnterEvent(self, event):
        if not self.busy and self.dropped_file(event.mimeData()) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        path = self.dropped_file(event.mimeData())
        if path is None or not self.can_open_file():
            event.ignore()
            return
        event.acceptProposedAction()
        # Let the OS finish the drop before displaying the import dialog.
        QTimer.singleShot(0, lambda: self.open_path(path))

    def detach(self):
        # Never close a connection while a queued page request still refers to it.
        self.count_generation += 1
        if self.model:
            self.model.generation += 1
        self.pool.waitForDone()
        if self.case:
            self.case.close()
        self.tree.setModel(None)
        if self.model:
            self.model.deleteLater()
        self.case, self.model = None, None
        self.content_stack.setCurrentIndex(0)
        self.source.clear()
        self.set_file_actions(False)
        self.cancel_action.setEnabled(False)
        self.setWindowTitle("Timeline Next")

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
            candidate = Case(path, settings=self.settings)
            if not candidate.headers:
                candidate.close()
                raise ValueError("Base vide ou import inachevé")
        except Exception as exc:
            self.error(exc)
            return
        self.detach()
        self.attach(candidate)

    def attach(self, case, initial_view=None, header_state=None):
        self.case = case
        self.content_stack.setCurrentIndex(1)
        self.set_file_actions(True)
        self.cancel_action.setEnabled(True)
        self.model = GridModel(case, self.pool, self)
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
        self.setWindowTitle(f"{name} - Timeline Next")
        self.source.setText(f"{name}  |  {len(case.headers)} colonnes")
        self.set_view(initial_view if initial_view is not None else View())
        if header_state is not None:
            self.tree.header().restoreState(header_state)

    def apply(self, *_):
        if not self.case or not self.model or self.busy:
            return
        self.view.search = self.search.text()
        self.view.bookmarks_only = self.only_notes.isChecked()
        self.view.sort_column = self.sort_column.currentData()
        self.view.sort_type = self.sort_type.currentData()
        self.view.descending = self.desc.isChecked()
        self.filters.clear()
        for f in self.view.filters:
            label = dict((v, k) for k, v in OPERATORS)[f.operator]
            self.filters.addItem(f"{self.case.headers[f.column]}  {label}  {f.value}")
        self.filters.setVisible(bool(self.view.filters))
        self.groups_label.setText("Groupement : " + " > ".join(self.case.headers[i] for i in self.view.groups) if self.view.groups else "Groupement : aucun")
        section = self.view.sort_column
        self.tree.header().setSortIndicatorShown(section is not None)
        if section is not None:
            self.tree.header().setSortIndicator(section + 1, Qt.DescendingOrder if self.view.descending else Qt.AscendingOrder)
        self.model.reset(self.view)
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
        self.set_view(View())

    def set_view(self, view):
        self.view = copy.deepcopy(view)
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
        del self.view.filters[self.filters.row(item)]
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
            item.setCheckState(Qt.Unchecked if self.tree.isColumnHidden(i) else Qt.Checked)
            listing.addItem(item)
            checks.append(item)
        layout.addWidget(listing)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec():
            for i, item in enumerate(checks, 1):
                self.tree.setColumnHidden(i, item.checkState() != Qt.Checked)

    def show_header_menu(self, position):
        header = self.tree.header()
        menu = header_menu(self, header.logicalIndexAt(position))
        if menu:
            menu.exec(header.mapToGlobal(position))
            menu.deleteLater()

    def show_cell_menu(self, position):
        index = self.tree.indexAt(position)
        menu = cell_menu(self, index)
        if menu:
            if not self.tree.selectionModel().isRowSelected(index.row(), index.parent()):
                self.tree.setCurrentIndex(index)
            menu.exec(self.tree.viewport().mapToGlobal(position))
            menu.deleteLater()

    def set_sort(self, column, descending=False, sort_type=None):
        if not self.case or self.busy or not 0 <= column < len(self.case.headers):
            return
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
        index = self.tree.currentIndex()
        if index.isValid():
            index = index.siblingAtColumn(0)
            if not self.model.node(index).group:
                index = index.parent()
        self.model.fetchMore(index)

    def previous(self):
        if not self.model:
            return
        index = self.tree.currentIndex()
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
            self.details.setPlainText(str(self.model.data(index.siblingAtColumn(0))))
        else:
            self.details.setPlainText(f"Ligne source : {node.values[0]}\nNote : {self.model.notes.get(node.values[0], '')}\n\n" + "\n\n".join(f"{h}\n{'∅' if v is None else v}" for h, v in zip(self.case.headers, node.values[1:])))

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
            case, model = self.case, self.model
            def work():
                case.bookmark(row_id, note or None)
                return case.bookmarks()
            def done(notes):
                model.notes = notes
                self.apply()
            self.run(work, done, exclusive=True)

    def save_view(self):
        if not self.case or self.busy:
            return
        name, ok = QInputDialog.getText(self, "Enregistrer la vue", "Nom (un nom existant sera remplacé)")
        if ok and name.strip():
            case, view = self.case, copy.deepcopy(self.view)
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
        target, _ = QFileDialog.getSaveFileName(self, "Exporter les résultats filtrés", "resultats.csv", "CSV (*.csv)")
        if not target:
            return
        grouped = False
        if self.view.groups:
            choice, ok = QInputDialog.getItem(self, "Export", "Contenu", ["Lignes filtrées", "Comptages par groupe"], 0, False)
            if not ok:
                return
            grouped = choice == "Comptages par groupe"
        case, view = self.case, copy.deepcopy(self.view)
        self.statusBar().showMessage("Export en cours…")
        self.run(lambda: case.export(target, view, grouped), lambda _: self.statusBar().showMessage(f"Export terminé : {target}"), exclusive=True)

    def integrity(self):
        if self.case and self.case.info:
            info = self.case.info
            QMessageBox.information(self, "Provenance de l’import", f"Source : {info['path']}\nOctets : {info['size']}\nLignes : {info['rows']}\nSHA-256 à l’import :\n{info['sha256']}\n\nLa source est lue sans modification. L’identifiant de ligne correspond à l’ordre des enregistrements CSV, hors en-tête (un enregistrement peut occuper plusieurs lignes physiques).")

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
        writer.writerow(self.case.headers)
        for index in self.tree.selectionModel().selectedRows():
            node = self.model.node(index)
            if not node.group:
                writer.writerow(node.values[1:])
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
    args = parser.parse_args()
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
    default_config = base / "timeline-next.toml"
    config = args.config if args.config is not None else default_config if default_config.exists() else None
    try:
        settings = load_settings(config)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    app = QApplication(sys.argv)
    app.setApplicationName("TimelineNext")
    apply_theme(app)
    if args.self_test_report is not None:
        from .windows_check import run_check
        raise SystemExit(run_check(app, args.self_test_report))
    window = Window(settings)
    window.show()
    if args.file is not None:
        QTimer.singleShot(0, lambda: window.open_path(args.file))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
