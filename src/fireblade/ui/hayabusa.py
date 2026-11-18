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

import time

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QSizePolicy, QAbstractItemView, QComboBox, QFrame, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QMenu, QPlainTextEdit,
                               QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from fireblade.core.assistant import Assistant, answer, install_model, install_runtime, write_manifest
from fireblade.core.explain import (SCHEMA, build_pack, describe_without_model, read_answer,
                                    render_structured, verify)
from fireblade.core.findings import group_alerts, group_alerts_sql, summarise
from fireblade.ui.maps import CircularMap, HeatMap, ChainMap

COLUMNS = ('Time', 'Level', 'Rule', 'Host', 'Count', 'Event IDs', 'MITRE')
VIEWS = (('Clock', CircularMap), ('Heat map', HeatMap), ('Chain', ChainMap))


def shrinkable(label):
    """A label that may be narrower than its text.

    The panel lives in a tab, and a tab's minimum width becomes the whole window's: a
    one-line summary long enough to be useful would otherwise stop Fireblade being usable
    on a 1024-pixel screen. The full text stays in the tooltip.
    """
    label.setWordWrap(False)
    label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    label.setMinimumWidth(0)
    label.setToolTip(label.text())
    return label


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
        self.state.setMinimumWidth(0)
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
        self.card.setMinimumHeight(38)
        self.card.setMinimumWidth(0)
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
        self.table.setMinimumWidth(0)
        self.table.itemSelectionChanged.connect(self.table_selection)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.grid_menu)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        for index in (0, 1, 3, 4, 5, 6):
            header.setSectionResizeMode(index, QHeaderView.ResizeToContents)
        lower = QSplitter(Qt.Vertical)
        lower.addWidget(self.table)

        detail_host = QWidget()
        detail = QHBoxLayout(detail_host)
        detail.setContentsMargins(0, 0, 0, 0)
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
        self.assistant_state = shrinkable(QLabel())
        side.addWidget(self.assistant_state)
        side.addStretch()
        detail.addLayout(side, 1)
        lower.addWidget(detail_host)
        lower.setSizes([220, 200])
        bottom_layout.addWidget(lower, 1)
        split.addWidget(bottom)
        split.setSizes([500, 300])
        layout.addWidget(split, 1)

        self.actions_row = QHBoxLayout()
        self.explain_button = QPushButton('Explain this finding')
        self.explain_button.setEnabled(False)
        self.explain_button.setToolTip('Ask the local model to read this finding and say what it shows.')
        self.explain_button.clicked.connect(self.explain_group)
        self.actions_row.addWidget(self.explain_button)
        self.setup_button = QPushButton('Set up the local model…')
        self.setup_button.setToolTip('Download the engine and the weights once; everything runs offline after that.')
        self.setup_button.clicked.connect(self.setup_assistant)
        self.actions_row.addWidget(self.setup_button)
        self.progress_label = shrinkable(QLabel())
        self.actions_row.addWidget(self.progress_label, 1)
        layout.addLayout(self.actions_row)

        self.status = shrinkable(QLabel())
        self.status.setFrameShape(QFrame.StyledPanel)
        layout.addWidget(self.status)
        # The panel is a tab of the workbench, so its minimum becomes the window's.
        self.setMinimumHeight(0)
        self.assistant_state.setText(self.assistant.status().detail)
        self._answers = {}
        self._busy_since = None
        self._ticker = QTimer(self)
        self._ticker.setInterval(1000)
        self._ticker.timeout.connect(self.tick_progress)
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
        # DuckDB groups the alerts: a folder that produced millions of rows never has to
        # fit in memory. The in-memory path stays as the fallback, and says so.
        self.mode = 'sql'
        try:
            with case.operation():
                self.groups, self.incidents = group_alerts_sql(case)
        except Exception as exc:                       # a broken analysis must say why
            try:
                self.rows = self.read_rows(case)
                self.groups, self.incidents = group_alerts(self.rows)
                # Samples are positions in that list; the rest of the panel addresses rows
                # by identifier, exactly as the SQL path does.
                for group in self.groups:
                    group.samples = [self.rows[index]['__row_id'] for index in group.samples
                                     if index < len(self.rows)]
                self.mode = 'python'
            except Exception as nested:
                self.groups, self.incidents, self.rows = [], [], []
                self.mode = 'none'
                self.state.setText('The Hayabusa table could not be read: %s (%s)' % (nested, exc))
                self.render()
                return
        self.summary = summarise(self.groups)
        self.selected = -1
        # 'incident' is a word the French heuristic flags, so the sentence avoids it.
        self.state.setText('%d alerts grouped into %d findings over %d time windows (%s).'
                           % (self.summary['hits'], self.summary['groups'], len(self.incidents),
                              'grouped in DuckDB' if self.mode == 'sql' else 'grouped in memory'))
        self.render()

    def read_rows(self, case):
        """Every alert row, as a dict keyed by the analysis' own column names."""
        headers = list(case.headers)
        wanted = self.wanted_columns(case)
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
        """The alert rows of one finding, read by identifier, bounded by the pack."""
        case = self.analysis()
        if case is None:
            return []
        ids = [int(value) for value in group.samples][:200]
        if not ids:
            return []
        wanted = self.wanted_columns(case)
        columns = ','.join('__row_id' if name == '__row_id' else case.column(case.headers.index(name))
                           for name in wanted)
        placeholders = ','.join('?' for _ in ids)
        with case.operation():
            rows = case.db.execute('SELECT %s FROM events WHERE __row_id IN (%s) ORDER BY __row_id'
                                   % (columns, placeholders), ids).fetchall()
        return [dict(zip(wanted, values)) for values in rows]

    def wanted_columns(self, case):
        names = [name for name in ('Timestamp', 'RuleTitle', 'Level', 'Computer', 'Channel', 'EventID',
                                   'MitreTactics', 'MitreTags', 'Details', 'DetailsShort', 'RuleID',
                                   'RuleFile', 'EvtxFile', 'RecordID') if name in case.headers]
        return ['__row_id'] + names

    def tick_progress(self):
        """A model call takes a minute: the panel says how long it has been running."""
        if self._busy_since is None:
            return
        elapsed = int(time.monotonic() - self._busy_since)
        self.progress_label.setText('The local model is reading this finding - %d s' % elapsed)

    def show_explanation(self, group):
        pack = build_pack(group, self.group_rows(group), self.groups, self.incidents)
        pack.links = []
        self._pack = pack
        chain = self.maps[ChainMap]
        chain.set_pack(pack)
        able = self.assistant.status().can_answer and bool(pack.facts)
        self.explain_button.setEnabled(able)
        self.ask_button.setEnabled(able)
        text = describe_without_model(pack)
        remembered = self._answers.get(group.key)
        if remembered:
            text += '\n\n--- local assistant ---\n' + remembered
        elif self.assistant.status().enabled:
            text += '\n\nAssistant: ' + self.assistant.status().detail
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
        """Answer a question about the selected finding, with the same guard as an explanation."""
        text = self.ask.text().strip()
        pack = getattr(self, '_pack', None)
        if not text:
            return
        if pack is None:
            self.explanation.appendPlainText('Select a finding first.')
            return
        self.ask.clear()
        self.explanation.appendPlainText('\n> ' + text)
        self.run_assistant(text)

    def explain_group(self):
        """Explain the selected finding with the local model, without freezing the window."""
        pack = getattr(self, '_pack', None)
        if pack is None or self.current_group() is None:
            return
        self.run_assistant('')

    def run_assistant(self, question):
        """One model call from a worker thread; both the button and the box go through it."""
        pack = getattr(self, '_pack', None)
        status = self.assistant.status()
        if self._busy_since is not None:
            # window.run queues a second job instead of refusing it, and two model calls
            # against one engine would only make both slower.
            self.progress_label.setText('An operation is already running; try again after it.')
            self.explanation.appendPlainText('\nA question is already running: this one was not sent.')
            return
        if pack is None or not status.can_answer:
            self.explanation.appendPlainText('The local assistant cannot answer: ' + status.detail)
            return
        if not question:
            self.explanation.appendPlainText('\nLocal assistant, reading %d event(s) of this finding…'
                                             % len(pack.facts))
        self._pending_question = question
        self.explain_button.setEnabled(False)
        self.ask_button.setEnabled(False)
        self._busy_since = time.monotonic()
        self._ticker.start()
        first = not getattr(self, '_engine_used', False)
        self.progress_label.setText('Loading the local model…' if first
                                    else 'The local model is reading %d event(s)…' % len(pack.facts))
        self.window.run(lambda: answer(str(self.assistant.root), pack, question, schema=SCHEMA),
                        self.explanation_ready, on_error=self.explanation_failed)

    def explanation_ready(self, result):
        self._busy_since = None
        self._ticker.stop()
        self._engine_used = True
        pack = getattr(self, '_pack', None)
        question = getattr(self, '_pending_question', '')
        self._pending_question = ''
        able = self.assistant.status().can_answer and bool(pack and pack.facts)
        self.explain_button.setEnabled(able)
        self.ask_button.setEnabled(able)
        self.progress_label.setText('')
        if not result or not result.get('ok'):
            self.explanation.appendPlainText('The local assistant did not answer: %s'
                                             % ((result or {}).get('text') or 'no reason given'))
            return
        decoded = read_answer(result.get('text', ''), pack)
        structured = decoded.get('structured') or {}
        structured['links'] = structured.get('links') or []
        pack.links = structured['links']
        self.maps[ChainMap].set_pack(pack)
        lines = []
        if decoded.get('valid'):
            lines.append(render_structured(structured))
        else:
            lines.append('The draft was discarded: '
                         + '; '.join(decoded.get('dropped') or ['the answer could not be read']))
        for item in decoded.get('dropped') or []:
            lines.append('Dropped: ' + item)
        cost = '%s s' % result.get('seconds')
        if result.get('completion_tokens'):
            cost += ' · %s tokens out' % result['completion_tokens']
        if question:
            cost += ' · answer to your question'
        rendered = '\n'.join(lines) + '\n(' + cost + ')'
        self.explanation.appendPlainText('\n' + rendered)
        if pack is not None and decoded.get('valid'):
            self._answers[pack.group_key] = rendered

    def explanation_failed(self, message):
        self._busy_since = None
        self._ticker.stop()
        self.explain_button.setEnabled(True)
        self.progress_label.setText('')
        self.explanation.appendPlainText('The local assistant failed: %s' % message)

    # ---------------------------------------------------------------- installation
    def setup_assistant(self):
        """Fetch the engine and the weights, with a progress the analyst can read."""
        self.setup_button.setEnabled(False)
        self.progress_label.setText('Starting the download…')
        root = str(self.assistant.root)
        job = InstallJob(self)
        self.install_job = job
        job.progress.connect(self.install_progress)
        job.done.connect(self.install_done)
        job.failed.connect(self.install_failed)
        job.start()

    def install_progress(self, received, total):
        if total:
            self.progress_label.setText('%d%% of %s MB downloaded · the window stays usable'
                                        % (int(100 * received / total), round(total / 1024 / 1024)))
        else:
            self.progress_label.setText('%s MB downloaded' % round(received / 1024 / 1024))

    def install_done(self, root):
        self.assistant = Assistant(root)
        status = self.assistant.status()
        self.assistant_state.setText(status.detail)
        self.progress_label.setText('Installed · ' + status.state)
        self.setup_button.setEnabled(True)
        group = self.current_group()
        if group is not None:
            self.show_explanation(group)

    def install_failed(self, message):
        self.setup_button.setEnabled(False)
        self.progress_label.setText('')
        self.explanation.appendPlainText('Installation failed: %s' % message)

    # ---------------------------------------------------------------- the grid
    def open_imports(self):
        index = self.window.workbench.indexOf(getattr(self.window, 'detection_panel', None))
        if index >= 0:
            self.window.workbench.setCurrentIndex(index)

    def grid_menu(self, point):
        index = self.table.indexAt(point).row()
        if index < 0:
            return
        item = self.table.item(index, 0)
        group = self.groups[int(item.data(Qt.UserRole))]
        menu = QMenu(self)
        menu.addAction('Show the alerts in the grid', lambda: self.open_in_grid(group))
        menu.addAction('Bookmark every alert of this finding', lambda: self.bookmark(group))
        menu.exec(self.table.viewport().mapToGlobal(point))

    def open_in_grid(self, group):
        """Leave this tab and search the case's own grid for the rule's alerts."""
        window = self.window
        if not window.documents or window.case is None:
            return
        target = next((i for i, snapshot in enumerate(window.documents)
                       if snapshot.path == str(window.case.path)), 0)
        window.switch_document(target)
        QTimer.singleShot(0, lambda: self.apply_search(group))

    def apply_search(self, group):
        """One search on the rule title, so the alert appears selected rather than hunted."""
        window = self.window
        if not getattr(window, 'model', None):
            return
        window.search.setText(group.title or '')
        window.search.returnPressed.emit()
        window.workbench.setCurrentIndex(0)

    def bookmark(self, group):
        case = getattr(self.window, 'case', None)
        if case is None:
            return
        ids = [int(self.rows[index]['__row_id']) for index in group.samples
               if isinstance(self.rows[index].get('__row_id'), (int, str))]
        if not ids:
            self.status.setText('Bookmarking needs the row identifiers of this analysis.')
            return
        try:
            case.bookmark_many(ids, 'Hayabusa: ' + group.title, mode='mark')
        except Exception as exc:
            self.status.setText('Bookmarking failed: %s' % exc)
            return
        self.status.setText('Bookmarked %d alert(s) of this finding.' % len(ids))


class InstallJob(QThread):
    """Download outside the UI thread: 1.6 GB over a home link is minutes, not seconds."""

    progress = Signal(int, int)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel

    def run(self):
        try:
            root = self.panel.assistant.root
            install_runtime(root, progress=lambda received, total: self.progress.emit(received, total))
            weights = install_model(root, progress=lambda received, total: self.progress.emit(received, total))
            name = weights.name if hasattr(weights, 'name') else 'MiniCPM5-2B-Q4_K_M.gguf'
            write_manifest(root, enabled=True, model=self.panel.assistant.model, weights=name)
            self.done.emit(str(root))
        except Exception as exc:            # a failed download must reach the panel, not the log
            self.failed.emit('%s: %s' % (type(exc).__name__, exc))
