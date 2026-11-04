"""Movable investigation panels, named layouts and lightweight persisted geometry."""
import base64
import json

from PySide6.QtCore import QByteArray, Qt, QTimer
from PySide6.QtWidgets import (QDockWidget, QHBoxLayout, QLabel, QMenu, QPushButton,
                             QTabWidget, QToolButton, QVBoxLayout, QWidget)
from fireblade.core.layout import write_json
from fireblade.runtime.windows_paths import user_directory


class Workbench(QTabWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.panels = {}
        self.setDocumentMode(True)
        self.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabBar().customContextMenuRequested.connect(self.panel_menu)

    def panel_menu(self, position):
        index = self.tabBar().tabAt(position)
        if index < 0 or not self.isTabEnabled(index):
            return
        menu = QMenu(self)
        menu.addAction('Rattacher' if index in self.panels else 'Détacher le panneau',
                       lambda: self.attach_panel(index) if index in self.panels else self.detach_panel(index))
        menu.exec(self.tabBar().mapToGlobal(position))

    def detach_panel(self, index, floating=False):
        if index in self.panels:
            dock = self.panels[index][1]
            dock.show(); dock.raise_()
            return dock
        if not 0 <= index < self.count() or not self.isTabEnabled(index):
            return None
        page, title = self.widget(index), self.tabText(index)
        placeholder = QWidget()
        layout = QVBoxLayout(placeholder)
        layout.addStretch()
        text = QLabel(title + ' · panneau détaché');text.setAlignment(Qt.AlignCenter)
        layout.addWidget(text)
        row = QHBoxLayout()
        for label, callback in [('Afficher', lambda: self.detach_panel(index)),
                                ('Rattacher', lambda: self.attach_panel(index))]:
            button = QPushButton(label);button.clicked.connect(callback);row.addWidget(button)
        layout.addLayout(row);layout.addStretch()
        blocked = self.blockSignals(True)
        self.removeTab(index);self.insertTab(index, placeholder, title);self.setCurrentIndex(index)
        self.blockSignals(blocked)
        dock = QDockWidget(title, self.window)
        dock.setObjectName('workspace-panel-' + str(index))
        dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        dock.setWidget(page)
        self.panels[index] = (page, dock, placeholder, title)
        self.window.addDockWidget(Qt.RightDockWidgetArea, dock)
        dock.resize(850, 650);dock.setFloating(floating);dock.show()
        return dock

    def attach_panel(self, index):
        item = self.panels.pop(index, None)
        if item is None:
            return
        page, dock, placeholder, title = item
        page.setParent(self)
        self.window.removeDockWidget(dock);dock.hide();dock.deleteLater()
        blocked = self.blockSignals(True)
        self.removeTab(index);self.insertTab(index, page, title);self.setCurrentIndex(index)
        self.blockSignals(blocked)
        placeholder.deleteLater()

    def indexOf(self, widget):
        for index, (page, *_rest) in self.panels.items():
            if page is widget:return index
        return super().indexOf(widget)

    def setCurrentWidget(self, widget):
        index = self.indexOf(widget)
        if index in self.panels:self.detach_panel(index)
        self.setCurrentIndex(index)


class WorkspaceLayout:
    def __init__(self, window):
        self.window = window
        self.focused = False
        self.pending_restore = False
        self.auxiliary = {}
        self.previous_visibility = []
        window.setDockNestingEnabled(True)
        window.menuBar().setStyleSheet("QMenuBar::item { padding: 4px 9px; }")
        window.main_toolbar.setObjectName("main-toolbar")
        window.main_toolbar.setMovable(True)
        window.collection_toolbar.setMovable(True)
        window.collection_toolbar.setObjectName("collection-toolbar")
        self.path = user_directory() / 'workspace-layout.json'
        menus = {a.text().replace('&', ''): a.menu() for a in window.menuBar().actions()}
        menu = menus['Affichage'].addMenu('Espace de travail')
        for title, function in [('Analyse', self.analysis), ('Chronologie seule', self.timeline),
                                ('Analyse + chronologie', self.side_by_side),
                                ('Rétablir les panneaux', self.reset), ('Enregistrer la disposition', self.save)]:
            menu.addAction(title, function)
        panels = menu.addMenu('Détacher / afficher un panneau')
        for index in range(window.workbench.count()):
            action = panels.addAction(window.workbench.tabText(index))
            action.triggered.connect(lambda _=False, i=index: window.workbench.detach_panel(i))
        panels.addSeparator()
        panels.addAction('Artefacts', lambda: self.detach_auxiliary('artifacts', window.navigator, window.workspace_splitter))
        panels.addAction('Détails de la ligne', lambda: self.detach_auxiliary('details', window.details, window.splitter))
        toolbar = window.addToolBar('Espace de travail');toolbar.setObjectName('workspace-toolbar')
        toolbar.setMovable(True)
        button = QToolButton();button.setText('Espace de travail');button.setPopupMode(QToolButton.InstantPopup)
        button.setMenu(menu);toolbar.addWidget(button)
        global_search = toolbar.addAction('Recherche globale');global_search.setShortcut('Ctrl+Shift+F3')
        global_search.triggered.connect(window.find_workspace)
        rule_action = toolbar.addAction('Règles', window.edit_rules)
        rule_action.setEnabled(window.case is not None);window.analysis_actions.append(rule_action)
        toolbar.addAction('Plugins', window.manage_plugins)
        def help_workspace():
            from fireblade.ui.help_dialogs import show_text
            from fireblade.runtime.resources import resource_path
            path = resource_path('docs/guides/ESPACE-DE-TRAVAIL.md')
            show_text(window, 'Espace de travail', path.read_text(encoding='utf-8'), markdown=True, base_url=path)
        menu.addSeparator();menu.addAction('Guide de l’espace de travail', help_workspace)
        self.toolbar = toolbar
        window.tree.header().sectionMoved.connect(self.schedule_columns)
        window.tree.header().sectionResized.connect(self.schedule_columns)
        for panel in window.tree.frozen_views:
            panel.header().setSectionsMovable(True)
            panel.header().setFirstSectionMovable(False)
            panel.header().sectionMoved.connect(lambda *_args, p=panel: self.sync_pinned_order(p))
        self.column_timer = QTimer(window);self.column_timer.setSingleShot(True)
        self.column_timer.setInterval(750);self.column_timer.timeout.connect(window.save_format_layout)
        window.analysis_add_bar.hide()
        window.details_action.toggled.connect(lambda visible: self.show_auxiliary('details', visible))
        window.navigation_action.toggled.connect(lambda visible: self.show_auxiliary('artifacts', visible))
        self.restore()

    def show_auxiliary(self, name, visible):
        if name in self.auxiliary:self.auxiliary[name][0].setVisible(visible)

    def detach_auxiliary(self, name, widget, splitter):
        if name in self.auxiliary:
            self.auxiliary[name][0].show();return
        position = splitter.indexOf(widget)
        dock = QDockWidget('Artefacts' if name == 'artifacts' else 'Détails de la ligne', self.window)
        dock.setObjectName('workspace-' + name);dock.setWidget(widget)
        self.auxiliary[name] = (dock, widget, splitter, position)
        self.window.addDockWidget(Qt.LeftDockWidgetArea if name == 'artifacts' else Qt.BottomDockWidgetArea, dock)
        dock.show();widget.show()
        dock.setContextMenuPolicy(Qt.CustomContextMenu)
        def context(point):
            menu = QMenu(dock);menu.addAction('Rattacher', lambda: self.attach_auxiliary(name));menu.exec(dock.mapToGlobal(point))
        dock.customContextMenuRequested.connect(context)

    def attach_auxiliary(self, name):
        dock, widget, splitter, position = self.auxiliary.pop(name)
        widget.setParent(splitter);splitter.insertWidget(max(0,position), widget)
        self.window.removeDockWidget(dock);dock.hide();dock.deleteLater()
        widget.show()

    def sync_pinned_order(self, panel):
        window = self.window
        if not window.model or window.tree._syncing:return
        right = panel is window.tree.right_frozen
        pinned = window.tree.right_pinned if right else window.tree.pinned
        ordered = [panel.header().logicalIndex(i) for i in range(panel.header().count()) if panel.header().logicalIndex(i) in pinned]
        if right:window.view.right_pinned_columns = [section-1 for section in ordered if section > 0];window.tree.right_pinned = ordered
        else:window.view.pinned_columns = [section-1 for section in ordered if section > 0];window.tree.pinned = ordered
        self.schedule_columns()

    def schedule_columns(self, *_):
        window = self.window
        if window.model and not window.busy and getattr(window, '_layout_save_enabled', False):
            self.column_timer.start()

    def leave_focus(self):
        if not self.focused:return
        for widget, visible in self.previous_visibility:widget.setVisible(visible)
        self.window.workbench.tabBar().show()
        self.focused = False
        self.window.timeline_panel.focus_button.setText("Agrandir")

    def analysis(self):
        self.leave_focus();self.window.workbench.setCurrentIndex(0)

    def timeline(self):
        self.leave_focus()
        window = self.window
        if not window.workbench.isTabEnabled(window.timeline_tab_index):return
        window.workbench.attach_panel(window.timeline_tab_index)
        window.show_timeline()
        widgets = [window.main_toolbar, window.collection_toolbar, window.statusBar()]
        self.previous_visibility = [(w, not w.isHidden()) for w in widgets]
        for widget, _visible in self.previous_visibility:widget.hide()
        for dock in window.findChildren(QDockWidget):
            self.previous_visibility.append((dock, not dock.isHidden()));dock.hide()
        window.workbench.tabBar().hide();self.focused = True
        window.timeline_panel.focus_button.setText("Rétablir")

    def side_by_side(self):
        self.leave_focus()
        self.window.show_timeline()
        self.window.workbench.detach_panel(self.window.timeline_tab_index)
        self.window.workbench.setCurrentIndex(0)
        self.window.resizeDocks([self.window.workbench.panels[self.window.timeline_tab_index][1]], [650], Qt.Horizontal)

    def reset(self):
        self.leave_focus()
        for name in list(self.auxiliary):self.attach_auxiliary(name)
        for index in list(self.window.workbench.panels):self.window.workbench.attach_panel(index)
        self.window.workbench.setCurrentIndex(0)
        self.window.main_toolbar.show();self.window.collection_toolbar.show()
        self.window.statusBar().show()

    def save(self):
        window = self.window
        focused = self.focused
        self.leave_focus()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            write_json(self.path, dict(version=1, detached=list(window.workbench.panels), auxiliary=list(self.auxiliary),
                state=base64.b64encode(window.saveState()).decode('ascii'),
                geometry=base64.b64encode(window.saveGeometry()).decode('ascii'), focus=focused,
                splitters={name:base64.b64encode(widget.saveState()).decode('ascii') for name, widget in
                    [('workspace',window.workspace_splitter),('details',window.splitter),('timeline',window.timeline_panel.splitter)]},
                timeline_header=base64.b64encode(window.timeline_panel.table.horizontalHeader().saveState()).decode('ascii'),
                timeline_widgets=dict(events=window.timeline_panel.events_visible.isChecked(),details=window.timeline_panel.details_visible.isChecked())))
            window.statusBar().showMessage('Disposition enregistrée')
        except (OSError, ValueError) as exc:window.statusBar().showMessage(str(exc))
        finally:
            if focused:self.timeline()

    def restore(self):
        if getattr(self.window, 'require_case', False) and self.window.active_investigation is None:
            self.pending_restore = True
            return
        self.pending_restore = False
        try:
            if not self.path.exists() or self.path.stat().st_size > 128*1024:return
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('version') != 1:return
            for index in data.get('detached', []):
                if type(index) is int:self.window.workbench.detach_panel(index)
            for name in data.get('auxiliary', []):
                if name == 'artifacts':self.detach_auxiliary(name, self.window.navigator, self.window.workspace_splitter)
                elif name == 'details':self.detach_auxiliary(name, self.window.details, self.window.splitter)
            self.window.restoreGeometry(QByteArray.fromBase64(data['geometry'].encode('ascii')))
            self.window.restoreState(QByteArray.fromBase64(data['state'].encode('ascii')))
            for name, widget in [('workspace',self.window.workspace_splitter),('details',self.window.splitter),('timeline',self.window.timeline_panel.splitter)]:
                value = data.get('splitters', {}).get(name)
                if isinstance(value, str):widget.restoreState(QByteArray.fromBase64(value.encode('ascii')))
            value = data.get('timeline_header')
            if isinstance(value, str):self.window.timeline_panel.table.horizontalHeader().restoreState(QByteArray.fromBase64(value.encode('ascii')))
            for key, widget in [('events', self.window.timeline_panel.events_visible), ('details', self.window.timeline_panel.details_visible)]:
                value = data.get('timeline_widgets', {}).get(key)
                if type(value) is bool:widget.setChecked(value)
            if data.get('focus'):self.timeline()
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            self.window.statusBar().showMessage('Disposition ignorée ; utilisez Affichage → Espace de travail.')
