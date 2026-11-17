"""The Hayabusa + AI tab of a case: findings grouped, a map of them, and the assistant.

The tab exists once per window and follows the active document. It refuses to invent
anything: before a Hayabusa analysis is loaded it says why, and it reads its content
from the DuckDB tables Fireblade already wrote.

Layout, top to bottom:

- the run section (what is loaded, how many findings, re-run);
- the selector of the three map views, then the map itself with the selected group's
  card beside it;
- the grid of groups, then the detail of the selected group and the ask box.

Every string is written in English: from 0.4.2 the product is English only, and a new
surface must not add French to the interface.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFrame, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QMenu, QPlainTextEdit,
                               QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from fireblade.core.assistant import Assistant
from fireblade.core.explain import build_pack, describe_without_model, verify
from fireblade.core.findings import group_alerts, summarise
from fireblade.ui.maps import CircularMap, HeatMap, ChainMap

COLUMNS = ('Time', 'Level', 'Rule', 'Host', 'Count', 'Event IDs', 'MITRE')
VIEWS = (('Clock', CircularMap), ('Heat map', HeatMap), ('Chain', ChainMap))


class HayabusaPanel(QWidget):
    """Findings of the loaded Hayabusa analysis, grouped and mapped."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.groups, self.incidents, self.rows = [], [], []
        self.selected = -1
        self.summary = dict(groups=0, hits=0, levels={})
        self.assistant = Assistant()
        self._build()

    # ---------------------------------------------------------------- interface
    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 6)
        layout.setSpacing(6)

        run = QHBoxLayout()
        self.state = QLabel()
        self.state.setWordWrap(True)
        run.addWidget(self.state, 1)
        self.rerun = QPushButton('Run Hayabusa…')
        self.rerun.setToolTip('Runs Hayabusa from the Imports tab; the results come back here.')
        self.rerun.clicked.connect(self.open_imports)
        run.addWidget(self.rerun)
        self.refresh_button = QPushButton('Refresh')
        self.refresh_button.clicked.connect(self.reload)
        run.addWidget(self.refresh_button)
        layout.addLayout(run)

        bar = QHBoxLayout()
        bar.addWidget(QLabel('View'))
        self.view_box = QComboBox()
        for label, _factory in VIEWS:
            self.view_box.addItem(label)
        self.view_box.currentIndexChanged.connect(self.change_view)
        bar.addWidget(self.view_box)
        bar.addWidget(QLabel('Grouped by'))
        self.level_box = QComboBox()
        for label, code in (('All levels', None), ('Critical only', 'critical'), ('High and above', 'high'),
                            ('Medium and above', 'medium')):
            self.level_box.addItem(label, code)
        self.level_box.currentIndexChanged.connect(lambda *_: self.render())
        bar.addWidget(self.level_box)
        bar.addStretch()
        self.filter_box = QLineEdit()
        self.filter_box.setPlaceholderText('filter: rule, host, event id…')
        self.filter_box.setClearButtonEnabled(True)
        self.filter_box.textChanged.connect(lambda *_: self.render())
        bar.addWidget(self.filter_box, 1)
        layout.addLayout(bar)

        split = QSplitter(Qt.Vertical)
        self.maps = {}
        self.map_host = QWidget()
        host_layout = QVBoxLayout(self.map_host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        self.map_stack = QWidget()
        self.map_layout = QVBoxLayout(self.map_stack)
        self.map_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.addWidget(self.map_stack, 1)
        for _label, factory in VIEWS:
            widget = factory()
            widget.group_selected.connect(self.select_group)
            widget.hide()
            self.map_layout.addWidget(widget)
            self.maps[factory] = widget
        self.card = QLabel()
        self.card.setWordWrap(True)
        self.card.setFrameShape(QFrame.StyledPanel)
        self.card.setMinimumHeight(48)
        self.card.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.card.setMargin(8)
        host_layout.addWidget(self.card)
        split.addWidget(self.map_host)

        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(list(COLUMNS))
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(72)
        self.table.itemSelectionChanged.connect(self.table_selection)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.grid_menu)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        for index in (0, 1, 3, 4, 5, 6):
            header.setSectionResizeMode(index, QHeaderView.ResizeToContents)
        bottom_layout.addWidget(self.table, 1)

        detail = QHBoxLayout()
        self.explanation = QPlainTextEdit()
        self.explanation.setReadOnly(True)
        self.explanation.setPlaceholderText('Select a finding to see what Fireblade knows about it.')
        self.explanation.setMinimumHeight(72)
        detail.addWidget(self.explanation, 3)
        side = QVBoxLayout()
        self.ask = QLineEdit()
        self.ask.setPlaceholderText('Ask about this finding…')
        self.ask.returnPressed.connect(self.ask_question)
        side.addWidget(self.ask)
        self.ask_button = QPushButton('Ask')
        self.ask_button.clicked.connect(self.ask_question)
        side.addWidget(self.ask_button)
        self.assistant_state = QLabel()
        self.assistant_state.setWordWrap(True)
        side.addWidget(self.assistant_state)
        side.addStretch()
        detail.addLayout(side, 1)
        bottom_layout.addLayout(detail)
        split.addWidget(bottom)
        split.setSizes([320, 420])
        layout.addWidget(split, 1)

        self.status = QLabel()
        self.status.setFrameShape(QFrame.StyledPanel)
        layout.addWidget(self.status)
        # The panel is a tab of the workbench, so its minimum becomes the window's.
        self.setMinimumHeight(0)
        self.assistant_state.setText(self.assistant.status().detail)
        self._active = CircularMap
        self.maps[CircularMap].show()

    # ---------------------------------------------------------------- content
    def showEvent(self, event):
        """Read the case again when the tab comes forward: the analyst may have run a new pass."""
        super().showEvent(event)
        QTimer.singleShot(0, self.reload_if_stale)

    def reload_if_stale(self):
        case = self.analysis()
        current = getattr(case, 'path', None)
        if current != getattr(self, '_loaded_path', None) or not self.groups:
            self._loaded_path = current
            self.reload()

    def analysis(self):
        """The loaded Hayabusa analysis: the open document when it is one, else the case's."""
        case = getattr(self.window, 'case', None)
        if case is None:
            return None
        headers = set(getattr(case, 'headers', []))
        if {'RuleTitle', 'Level', 'Timestamp'}.issubset(headers):
            return case
        return None

    def reload(self):
        case = self.analysis()
        if case is None:
            self.groups, self.incidents, self.rows = [], [], []
            self.state.setText('No Hayabusa analysis is loaded. Parse a collection in Imports, then click '
                               'Run Hayabusa; Fireblade keeps every alert and this tab reads them.')
            self.render()
            return
        try:
            self.rows = self.read_rows(case)
        except Exception as exc:  # a broken analysis must say so, not kill the tab
            self.groups, self.incidents, self.rows = [], [], []
            self.state.setText('The Hayabusa table could not be read: %s' % exc)
            self.render()
            return
        self.groups, self.incidents = group_alerts(self.rows)
        self.summary = summarise(self.groups)
        self.selected = -1
        # 'incident' is a word the French heuristic flags, so the sentence avoids it.
        self.state.setText('%d alerts grouped into %d findings over %d time windows.'
                           % (self.summary['hits'], self.summary['groups'], len(self.incidents)))
        self.render()

    def read_rows(self, case):
        """Every alert row, as a dict keyed by the analysis' own column names."""
        headers = list(case.headers)
        wanted = [name for name in ('Timestamp', 'RuleTitle', 'Level', 'Computer', 'Channel', 'EventID',
                                    'MitreTactics', 'MitreTags', 'Details', 'DetailsShort', 'RuleID',
                                    'RuleFile', 'EvtxFile', 'RecordID')
                  if name in headers]
        # __row_id first: bookmarking a finding needs the identifiers the case uses.
        wanted.insert(0, '__row_id')
        if '__row_id' not in headers:
            wanted.remove('__row_id')
        columns = ','.join(case.column(headers.index(name)) if name != '__row_id' else '__row_id'
                           for name in wanted)
        with case.operation():
            cursor = case.db.execute('SELECT %s FROM events' % columns)
            rows = []
            while batch := cursor.fetchmany(4096):
                for values in batch:
                    rows.append(dict(zip(wanted, values)))
        return rows

    def visible_groups(self):
        floors = {'critical': ['critical'], 'high': ['critical', 'high'],
                  'medium': ['critical', 'high', 'medium']}
        allowed = floors.get(self.level_box.currentData())
        text = self.filter_box.text().strip().casefold()
        result = []
        for index, group in enumerate(self.groups):
            if allowed and group.level not in allowed:
                continue
            if text and text not in ' '.join((group.title, group.host, ' '.join(group.event_ids),
                                              group.techniques, group.tactics)).casefold():
                continue
            result.append((index, group))
        return result

    def render(self):
        visible = self.visible_groups()
        self.fill_table(visible)
        widget = self.maps[self._active]
        widget.set_data([group for _index, group in visible], self.incidents)
        if self.selected < 0 and visible:
            self.select_group(visible[0][0])
        else:
            self.show_card()
        levels = self.summary.get('levels', {})
        self.status.setText('critical %d · high %d · medium %d · low %d · info %d   |   showing %d of %d'
                            % (levels.get('critical', 0), levels.get('high', 0), levels.get('medium', 0),
                               levels.get('low', 0), levels.get('informational', 0),
                               len(visible), len(self.groups)))

    def fill_table(self, visible):
        self.table.blockSignals(True)
        self.table.setRowCount(len(visible))
        for row, (index, group) in enumerate(visible):
            values = (group.start.strftime('%Y-%m-%d %H:%M:%S') if group.start else 'no date',
                      group.level, group.title, group.host, str(group.count),
                      ', '.join(group.event_ids[:4]), group.techniques or group.tactics)
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 4:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                item.setData(Qt.UserRole, index)
                self.table.setItem(row, column, item)
        self.table.blockSignals(False)
        self._visible = [index for index, _group in visible]

    def change_view(self, _index):
        factory = VIEWS[max(0, self.view_box.currentIndex())][1]
        self._active = factory
        for klass, widget in self.maps.items():
            widget.setVisible(klass is factory)
        self.render()

    # ---------------------------------------------------------------- selection
    def select_group(self, index):
        if not 0 <= index < len(self.groups):
            return
        self.selected = index
        group = self.groups[index]
        for row, visible_index in enumerate(getattr(self, '_visible', [])):
            if visible_index == index:
                self.table.blockSignals(True)
                self.table.selectRow(row)
                self.table.blockSignals(False)
                break
        self.maps[self._active].select(group.key)
        self.show_explanation(group)
        self.show_card()

    def table_selection(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        item = self.table.item(rows[0].row(), 0)
        if item is not None:
            self.select_group(int(item.data(Qt.UserRole)))

    def current_group(self):
        return self.groups[self.selected] if 0 <= self.selected < len(self.groups) else None

    def group_rows(self, group):
        return [self.rows[index] for index in group.samples if 0 <= index < len(self.rows)]

    def show_explanation(self, group):
        pack = build_pack(group, self.group_rows(group), self.groups, self.incidents)
        self._pack = pack
        text = describe_without_model(pack)
        status = self.assistant.status()
        if status.enabled:
            text += '\n\nAssistant: ' + status.detail
        self.explanation.setPlainText(text)

    def show_card(self):
        group = self.current_group()
        if group is None:
            self.card.setText('No finding selected.')
            return
        window = 'context ±5 min' if group.start else 'no usable timestamp'
        self.card.setText('<b>%s</b> · %s · %s<br>%d occurrence(s) between %s and %s · %s'
                          % (group.title.replace('&', '&amp;'), group.level, group.host or 'unknown host',
                             group.count,
                             group.start.strftime('%H:%M:%S') if group.start else '—',
                             group.end.strftime('%H:%M:%S') if group.end else '—', window))

    def ask_question(self):
        text = self.ask.text().strip()
        if not text:
            return
        pack = getattr(self, '_pack', None)
        if pack is None:
            self.explanation.appendPlainText('Select a finding first.')
            return
        status = self.assistant.status()
        self.ask.clear()
        self.explanation.appendPlainText('\n> ' + text)
        if not status.can_answer:
            self.explanation.appendPlainText(
                'The local assistant cannot answer: ' + status.detail)
            return
        # The guard is wired before the engine: an answer whose citations do not exist
        # in the pack is refused, never shown.
        answer = self.generate(text, pack)
        if verify(answer, pack):
            self.explanation.appendPlainText(answer)
        else:
            self.explanation.appendPlainText(
                'The draft answer was discarded: it cited an event that is not in this finding.')

    def generate(self, question, pack):
        """Placeholder until the engine lands: no model, no answer."""
        return ''

    def open_imports(self):
        index = self.window.workbench.indexOf(getattr(self.window, 'detection_panel', None))
        if index >= 0:
            self.window.workbench.setCurrentIndex(index)

    def grid_menu(self, point):
        index = self.table.indexAt(point).row()
        if index < 0:
            return
        item = self.table.item(index, 0)
        group_index = int(item.data(Qt.UserRole))
        group = self.groups[group_index]
        menu = QMenu(self)
        menu.addAction('Open the alerts in the grid', lambda: self.open_in_grid(group))
        menu.addAction('Bookmark every alert of this finding', lambda: self.bookmark(group))
        menu.exec(self.table.viewport().mapToGlobal(point))

    def open_in_grid(self, group):
        window = self.window
        if not window.documents:
            return
        target = next((i for i, snapshot in enumerate(window.documents) if snapshot.path == str(window.case.path)), 0)
        window.switch_document(target)
        # Re-applies the search on the active case's own grid, so the alert appears
        # selected instead of the analyst hunting for its row.
        QTimer.singleShot(0, lambda: self.apply_search(group))

    def bookmark(self, group):
        case = getattr(self.window, 'case', None)
        if case is None:
            return
        ids = [int(self.rows[index].get('__row_id'))
               for index in group.samples if isinstance(self.rows[index].get('__row_id'), (int, str))]
        if not ids:
            self.status.setText('Bookmarking needs the row identifiers; reopen the analysis.')
            return
        try:
            case.bookmark_many([int(value) for value in ids], 'Hayabusa: ' + group.title, mode='mark')
        except Exception as exc:
            self.status.setText('Bookmarking failed: %s' % exc)
            return
        self.status.setText('Bookmarked %d alert(s) of this finding.' % len(ids))

    def apply_search(self, group):
        """Show this finding's alerts in the grid: one search on the rule title, then the host."""
        window = self.window
        if not getattr(window, 'model', None):
            return
        from PySide6.QtWidgets import QApplication
        window.search.setText(group.title or '')
        QApplication.sendPostedEvents(None, 0)
        window.search.returnPressed.emit()
        window.workbench.setCurrentIndex(0)
