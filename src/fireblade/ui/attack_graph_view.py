"""The attack-graph tab: the case's hosts, techniques and indicators, tagged by hand.

The graph itself is built in :mod:`fireblade.core.attack_graph` from the findings, the
tracked indicators and the declared machines; this widget draws it, lets the analyst move
a node, tag it, and export the picture into the client report.

Only what the analyst touched is written back to ``workspace.json``: generated nodes are
rebuilt from the data every time, so a rebuild after a new Hayabusa run keeps the tags
without freezing a stale list of hosts.
"""
from __future__ import annotations

from PySide6.QtCore import QBuffer, QIODevice, QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QMenu, QMessageBox, QPlainTextEdit,
                               QPushButton, QToolButton, QVBoxLayout, QWidget)

from fireblade.core import case_workspace
from fireblade.core.attack_graph import TACTICS, build, layout
from fireblade.core.model_texts import NODE_LABELS

COLOURS = {
    'host': QColor('#174b73'),
    'account': QColor('#2f6f8f'),
    'technique': QColor('#8b320c'),
    'stage': QColor('#3f6b3f'),
    'ioc': QColor('#6b3f8b'),
    'custom': QColor('#4f6074'),
}


class TagDialog(QDialog):
    def __init__(self, parent=None, node=None):
        super().__init__(parent)
        self.setWindowTitle('Étiquettes du nœud')
        self.resize(460, 320)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"{node.get('label', '')} — {NODE_LABELS.get(node.get('kind'), '')}"))
        self.existing = QPlainTextEdit()
        self.existing.setPlainText('\n'.join(node.get('tags') or []))
        layout.addWidget(QLabel('Une étiquette par ligne :'))
        layout.addWidget(self.existing, 1)
        row = QHBoxLayout()
        self.suggestions = QComboBox()
        self.suggestions.addItems([tactic for tactic in TACTICS] + ['Compromission confirmée', 'À vérifier',
                                                                    'Persistance', 'Exfiltration', 'Faux positif'])
        row.addWidget(self.suggestions, 1)
        add = QPushButton('Ajouter')
        add.clicked.connect(self.add_suggestion)
        row.addWidget(add)
        layout.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def add_suggestion(self):
        text = self.suggestions.currentText()
        lines = [line for line in self.existing.toPlainText().splitlines() if line.strip()]
        if text and text not in lines:
            lines.append(text)
            self.existing.setPlainText('\n'.join(lines))

    def tags(self):
        result = []
        for line in self.existing.toPlainText().splitlines():
            tag = line.strip()[:40]
            if tag and tag.casefold() not in [item.casefold() for item in result]:
                result.append(tag)
        return result[:20]


class GraphCanvas(QWidget):
    """Draws the graph; dragging a node moves it, dragging the background pans."""

    node_selected = Signal(str)
    node_moved = Signal(str)
    node_activated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.graph = dict(nodes=[], edges=[])
        self.selected = None
        self.scale = 1.0
        self.offset = QPointF(30, 20)
        self._drag = None
        self._pan = None
        self.setMouseTracking(True)
        self.setMinimumSize(400, 300)

    def set_graph(self, graph):
        self.graph = graph
        layout(graph)
        self.selected = None
        self.fit()
        self.update()

    def fit(self):
        """Scale and pan so the whole graph is visible, never past the readability floor."""
        nodes = self.graph.get('nodes', [])
        if not nodes:
            self.scale, self.offset = 1.0, QPointF(30, 20)
            return
        min_x = min(node.get('x', 0) for node in nodes)
        min_y = min(node.get('y', 0) for node in nodes)
        max_x = max(node.get('x', 0) for node in nodes) + 200
        max_y = max(node.get('y', 0) for node in nodes) + 60
        width = max(1, self.width() - 40)
        span = max(1, max_x - min_x)
        self.scale = max(0.35, min(1.0, width / span))
        self.offset = QPointF(20 - min_x * self.scale, 20 - min_y * self.scale)

    def node_at(self, point):
        for node in reversed(self.graph.get('nodes', [])):
            rect = self.rect_of(node)
            if rect.contains(point):
                return node
        return None

    def rect_of(self, node):
        width, height = self.size_of(node)
        position = self.position_of(node)
        return QRectF(position.x(), position.y() - height + 8, width, height)

    def position_of(self, node):
        return QPointF((node.get('x', 0)) * self.scale + self.offset.x(),
                       (node.get('y', 0)) * self.scale + self.offset.y())

    def size_of(self, node):
        tags = node.get('tags') or []
        width = 190 if node.get('kind') != 'stage' else 160
        height = 34 if not tags else 46
        return width * self.scale, height * self.scale

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        background = QLinearGradient(0, 0, 0, self.height())
        background.setColorAt(0, QColor('#fbfdff'))
        background.setColorAt(1, QColor('#eef3f8'))
        painter.fillRect(self.rect(), background)
        nodes = self.graph.get('nodes', [])
        if not nodes:
            painter.setPen(QColor('#4f6074'))
            painter.drawText(self.rect().adjusted(24, 24, -24, -24), Qt.TextWordWrap,
                             'Aucun nœud. Lancez Hayabusa sur une analyse, puis cliquez sur Reconstruire : '
                             'les hôtes, les techniques et les indicateurs suivis apparaîtront ici.')
            return
        painter.setPen(QPen(QColor('#b8c6d4'), max(1, self.scale)))
        for edge in self.graph.get('edges', []):
            source = next((item for item in nodes if item['id'] == edge.get('source')), None)
            target = next((item for item in nodes if item['id'] == edge.get('target')), None)
            if source is None or target is None or source is target:
                continue
            start_rect, end_rect = self.rect_of(source), self.rect_of(target)
            if end_rect.left() < start_rect.left():
                start = QPointF(start_rect.left(), start_rect.center().y())
                end = QPointF(end_rect.right(), end_rect.center().y())
            else:
                start = QPointF(start_rect.right(), start_rect.center().y())
                end = QPointF(end_rect.left(), end_rect.center().y())
            painter.drawLine(start, end)
        for node in nodes:
            rect = self.rect_of(node)
            colour = COLOURS.get(node.get('kind'), COLOURS['custom'])
            path = QPainterPath()
            path.addRoundedRect(rect, 7, 7)
            fill = QColor('#ffffff') if node.get('id') != self.selected else QColor('#fff3c4')
            painter.fillPath(path, fill)
            painter.setPen(QPen(colour, 2 if node.get('id') == self.selected else 1.4))
            painter.drawPath(path)
            font = QFont(self.font())
            font.setBold(True)
            font.setPointSizeF(max(7.5, 9.5 * self.scale))
            painter.setFont(font)
            painter.setPen(colour)
            label = str(node.get('label', ''))
            painter.drawText(rect.adjusted(8, 4, -8, -4), Qt.AlignLeft | Qt.AlignTop | Qt.TextSingleLine,
                             painter.fontMetrics().elidedText(label, Qt.ElideRight, int(rect.width() - 16)))
            tags = node.get('tags') or []
            if tags:
                font.setBold(False)
                font.setPointSizeF(max(6.5, 8 * self.scale))
                painter.setFont(font)
                painter.setPen(QColor('#4f6074'))
                text = ', '.join(tags)
                painter.drawText(rect.adjusted(8, 20 * self.scale, -8, -2), Qt.AlignLeft | Qt.AlignTop,
                                 painter.fontMetrics().elidedText(text, Qt.ElideRight, int(rect.width() - 16)))

    def mousePressEvent(self, event):
        point = QPointF(event.position())
        node = self.node_at(point)
        self._drag = None
        self._pan = None
        if node is not None:
            self.selected = node['id']
            self.node_selected.emit(node['id'])
            self._drag = (node, point - self.position_of(node))
        else:
            self.selected = None
            self._pan = point
            self.node_selected.emit('')
        self.update()

    def mouseMoveEvent(self, event):
        point = QPointF(event.position())
        if self._drag is not None:
            node, delta = self._drag
            node['x'] = round((point.x() - delta.x() - self.offset.x()) / self.scale)
            node['y'] = round((point.y() - delta.y() - self.offset.y()) / self.scale)
            self.update()
        elif self._pan is not None:
            self.offset += point - self._pan
            self._pan = point
            self.update()

    def mouseDoubleClickEvent(self, event):
        node = self.node_at(QPointF(event.position()))
        if node is not None:
            self.selected = node['id']
            self.node_activated.emit(node['id'])
            self.update()

    def mouseReleaseEvent(self, event):
        if self._drag is not None:
            self.node_moved.emit(self._drag[0]['id'])
        self._drag = None
        self._pan = None

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale = max(0.35, min(2.5, self.scale * factor))
        self.update()

    def render_png(self):
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        self.grab().save(buffer, 'PNG')
        return bytes(buffer.data())


class AttackGraphPanel(QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.workspace = None
        self.touched = set()
        self._build()
        self.canvas.set_graph(dict(nodes=[], edges=[]))

    def _build(self):
        layout_box = QVBoxLayout(self)
        layout_box.setContentsMargins(8, 8, 8, 6)
        title = QLabel('Graphe d\'attaque')
        title.setStyleSheet('font-size: 18px; font-weight: bold;')
        layout_box.addWidget(title)
        hint = QLabel('Hôtes, techniques observées et indicateurs suivis, ordonnés selon la chaîne '
                      'd\'attaque. Double-cliquez un nœud pour lui poser des étiquettes ; elles sont '
                      'enregistrées dans le case et reprises dans le rapport client.')
        hint.setWordWrap(True)
        layout_box.addWidget(hint)
        bar = QHBoxLayout()
        self.rebuild_button = QPushButton('Reconstruire')
        self.rebuild_button.setToolTip('Reconstruire depuis les constats')
        self.rebuild_button.clicked.connect(self.reload)
        bar.addWidget(self.rebuild_button)
        self.level = QComboBox()
        for label, code in (('Tous les niveaux', None), ('Élevé et au-dessus', 'high'),
                            ('Critique uniquement', 'critical')):
            self.level.addItem(label, code)
        self.level.currentIndexChanged.connect(lambda *_: self.reload(reload_workspace=False))
        bar.addWidget(self.level)
        bar.addWidget(QLabel('Zoom :'))
        zoom_in = QPushButton('+')
        zoom_in.clicked.connect(lambda: self.zoom(1.2))
        bar.addWidget(zoom_in)
        zoom_out = QPushButton('−')
        zoom_out.clicked.connect(lambda: self.zoom(1/1.2))
        bar.addWidget(zoom_out)
        reset = QPushButton('Recentrer')
        reset.clicked.connect(self.reset_view)
        bar.addWidget(reset)
        tag = QPushButton('Étiqueter…')
        tag.clicked.connect(self.tag_selected)
        bar.addWidget(tag)
        # One menu button, not three: the tab's minimum width decides the window's, and
        # three more labels would push Fireblade past a 1024-pixel screen.
        more = QToolButton()
        more.setText('⋯')
        more.setToolTip('Nœud libre et export de l\'image')
        menu = QMenu(more)
        menu.addAction('Nœud libre…', self.add_node)
        menu.addAction('Exporter PNG…', self.export_png)
        menu.addAction('Couche ATT&CK Navigator…', self.export_navigator)
        more.setMenu(menu)
        more.setPopupMode(QToolButton.InstantPopup)
        bar.addWidget(more)
        bar.addStretch()
        layout_box.addLayout(bar)
        self.canvas = GraphCanvas()
        self.canvas.node_selected.connect(self.show_node)
        self.canvas.node_moved.connect(self.node_moved)
        self.canvas.node_activated.connect(lambda node_id: self.tag_selected())
        layout_box.addWidget(self.canvas, 1)
        self.details = QLabel()
        self.details.setTextFormat(Qt.PlainText)
        self.details.setWordWrap(True)
        layout_box.addWidget(self.details)
        self.status = QLabel()
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout_box.addWidget(self.status)

    def active_case(self):
        return getattr(self.window, 'active_investigation', None)

    def folder(self):
        case = self.active_case()
        return self.window.investigation_library.folder(case['id']) if case else None

    def reload(self, reload_workspace=True):
        case = self.active_case()
        if case is None:
            self.canvas.set_graph(dict(nodes=[], edges=[]))
            self.status.setText('Ouvrez un case pour construire son graphe d\'attaque.')
            return
        try:
            if reload_workspace or self.workspace is None:
                self.workspace = case_workspace.load(self.folder())
        except (OSError, ValueError) as exc:
            self.window.error(str(exc))
            return
        panel = getattr(self.window, 'hayabusa_panel', None)
        if panel is not None:
            panel.reload_if_stale()
        groups = list(getattr(panel, 'groups', []) or []) if panel else []
        level = self.level.currentData()
        if level == 'high':
            groups = [item for item in groups if item.level in ('critical', 'high')]
        elif level == 'critical':
            groups = [item for item in groups if item.level == 'critical']
        try:
            graph = build(groups, self.workspace)
        except ValueError as exc:
            self.window.error(str(exc))
            return
        self.touched.clear()
        self.canvas.set_graph(graph)
        self.status.setText(f'{len(graph["nodes"])} nœud(s) · {len(graph["edges"])} lien(s) · '
                            f'{len(groups)} constat(s) source. Les étiquettes posées ici sont '
                            'conservées dans le case.')

    def zoom(self, factor):
        self.canvas.scale = max(0.35, min(2.5, self.canvas.scale * factor))
        self.canvas.update()

    def reset_view(self):
        self.canvas.fit()
        self.canvas.update()

    def selected_node(self):
        return next((node for node in self.canvas.graph.get('nodes', [])
                     if node['id'] == self.canvas.selected), None)

    def show_node(self, node_id):
        node = self.selected_node()
        if node is None:
            self.details.clear()
            return
        tags = ', '.join(node.get('tags') or []) or 'aucune'
        self.details.setText(f"{node.get('label')} · {NODE_LABELS.get(node.get('kind'), '')} · "
                             f"étiquettes : {tags}")

    def tag_selected(self):
        node = self.selected_node()
        if node is None:
            self.window.error('Sélectionnez un nœud du graphe.')
            return
        dialog = TagDialog(self, node)
        try:
            if dialog.exec() != QDialog.Accepted:
                return
            node['tags'] = dialog.tags()
            self.touched.add(node['id'])
            self.persist()
            self.canvas.update()
            self.show_node(node['id'])
        finally:
            dialog.deleteLater()

    def add_node(self):
        if self.active_case() is None:
            self.window.error('Ouvrez un case avant d\'ajouter un nœud.')
            return
        label, accepted = QInputDialog.getText(self, 'Nœud libre', 'Nom du nœud :')
        if not accepted or not label.strip():
            return
        tags, accepted = QInputDialog.getText(self, 'Étiquettes', 'Étiquettes (séparées par des virgules) :')
        try:
            case_workspace.tag_node(self.folder(), label.strip(),
                                    tags=[tag.strip() for tag in (tags or '').split(',') if tag.strip()])
        except (OSError, ValueError) as exc:
            self.window.error(str(exc))
            return
        self.reload()

    def node_moved(self, node_id):
        self.touched.add(node_id)
        self.persist()

    def persist(self):
        """Write back only the nodes the analyst moved or tagged."""
        if not self.touched or self.workspace is None:
            return
        nodes = {node['id']: node for node in self.canvas.graph.get('nodes', [])}
        folder = self.folder()

        def change(data):
            existing = {node['id']: node for node in data['graph']['nodes']}
            for identifier in sorted(self.touched):
                node = nodes.get(identifier)
                if node is None:
                    continue
                existing[identifier] = dict(id=identifier, label=node.get('label', identifier),
                                            kind=node.get('kind', 'custom'),
                                            tags=list(node.get('tags') or []),
                                            x=node.get('x'), y=node.get('y'))
            data['graph']['nodes'] = list(existing.values())
        try:
            self.workspace = case_workspace.mutate(folder, change)
        except (OSError, ValueError) as exc:
            self.window.error(str(exc))

    def export_navigator(self):
        """The techniques of this case, as a layer the official Navigator opens."""
        import json
        from pathlib import Path
        from fireblade.core.attack_graph import navigator_layer
        graph = self.canvas.graph
        if not any(node.get('kind') == 'technique' for node in graph.get('nodes', [])):
            self.window.error('Aucune technique MITRE dans ce graphe : rien à exporter pour le Navigator.')
            return
        case = getattr(self.window, 'active_investigation', None) or {}
        label = case.get('name') or 'Fireblade'
        layer = navigator_layer(graph, name='Fireblade — '+str(label),
                                description='Techniques observed in the case, as Fireblade read them.',
                                case=label)
        if not layer['techniques']:
            self.window.error('Aucune technique identifiée par un identifiant ATT&CK (Txxxx) : rien à exporter.')
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Exporter la couche ATT&CK Navigator',
                                              'fireblade-attack-layer.json', 'Couche Navigator (*.json)')
        if not path:
            return
        if not path.casefold().endswith('.json'):
            path += '.json'
        try:
            Path(path).write_text(json.dumps(layer, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError as exc:
            self.window.error('La couche n’a pas pu être enregistrée : '+str(exc))
            return
        self.status.setText(f"Couche ATT&CK Navigator exportée : {path} ({len(layer['techniques'])} techniques)")

    def export_png(self):
        from PySide6.QtWidgets import QFileDialog
        if not self.canvas.graph.get('nodes'):
            self.window.error('Le graphe est vide.')
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Exporter le graphe', 'graphe-attaque.png',
                                              'Image PNG (*.png)')
        if not path:
            return
        if not path.casefold().endswith('.png'):
            path += '.png'
        if self.canvas.grab().save(path, 'PNG'):
            self.status.setText('Graphe exporté : ' + path)
        else:
            self.window.error('L\'image n\'a pas pu être enregistrée.')
