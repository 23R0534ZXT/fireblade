"""Navigate small analysis snapshots without opening inactive databases."""
from pathlib import Path, PurePosixPath

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget


class AnalysisNavigator(QWidget):
    activated = Signal(int)
    close_requested = Signal()
    grouping_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.signature = None
        self.family_cache = {}
        self.setMinimumWidth(140)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 4, 0)
        heading=QHBoxLayout();heading.addWidget(QLabel('Artefacts'),1)
        close=QToolButton();close.setText('×');close.setToolTip('Masquer la navigation ; la retrouver dans Affichage.')
        close.clicked.connect(self.close_requested.emit);heading.addWidget(close);layout.addLayout(heading)
        self.grouping = QComboBox()
        for label, value in [('Par artefact', 'families'), ('Par dossier source', 'folders'), ('Liste simple', 'flat')]:
            self.grouping.addItem(label, value)
        self.grouping.currentIndexChanged.connect(lambda _: self.grouping_changed.emit(self.grouping.currentData()))
        layout.addWidget(self.grouping)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Filtrer les noms d’artefacts…')
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter)
        layout.addWidget(self.search)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setUniformRowHeights(True)
        self.tree.itemActivated.connect(self.activate)
        self.tree.itemClicked.connect(self.activate)
        layout.addWidget(self.tree)

    def activate(self, item, *_):
        index = item.data(0, Qt.UserRole)
        if index is not None:
            self.activated.emit(index)

    def refresh(self, documents, active, collections, labels=None, origins=None, grouping="families"):
        blocked = self.grouping.blockSignals(True)
        self.grouping.setCurrentIndex(self.grouping.findData(grouping))
        self.grouping.blockSignals(blocked)
        labels=labels or {}
        origins=origins or {}
        signature = (tuple((d.path, d.source_info['path']) for d in documents),
                     tuple((c['path'], c['name']) for c in collections),
                     tuple(labels.get(d.path,'') for d in documents), grouping,
                     tuple((d.path, str(origins.get(d.path, {}))) for d in documents))
        if signature != self.signature:
            expanded = {self.key(item): item.isExpanded() for item in self.items()}
            self.family_cache = {d.path:self.family_cache[d.path] for d in documents if d.path in self.family_cache}
            self.tree.clear()
            roots, families, folders = {}, {}, {}
            for owner in collections:
                root_key = owner['path']
                roots[root_key] = QTreeWidgetItem(self.tree, [owner['name']])
                roots[root_key].setData(0, Qt.UserRole+1, root_key)
                roots[root_key].setToolTip(0, root_key)
            for index, snapshot in enumerate(documents):
                owner = next((c for c in collections if Path(c['path']) in Path(snapshot.path).parents), None)
                root_key = owner['path'] if owner else ''
                if root_key not in roots:
                    roots[root_key] = QTreeWidgetItem(self.tree, [owner['name'] if owner else 'Analyses hors collecte'])
                    roots[root_key].setData(0, Qt.UserRole+1, root_key)
                    roots[root_key].setToolTip(0, root_key)
                source = Path(snapshot.source_info['path'])
                if snapshot.path not in self.family_cache:
                    self.family_cache[snapshot.path] = artifact_family(snapshot.source_info, source)
                family = ('Détection Hayabusa' if 'hayabusa' in source.stem.casefold() else
                          'Contexte EVTX' if source.stem == 'Contexte EVTX' else self.family_cache[snapshot.path])
                origin = origins.get(snapshot.path)
                if origin and origin.get('artifact'):
                    family = origin['artifact']
                if grouping == 'flat' or grouping == 'folders' and origin:
                    parent = roots[root_key]
                    if grouping == 'folders' and origin:
                        relative = PurePosixPath(origin.get('relative', '').replace('\\', '/'))
                        components = [origin.get('partition', 'Volume'), *relative.parent.parts]
                        key = root_key
                        for component in components:
                            key += '|'+component
                            if key not in folders:
                                folder = QTreeWidgetItem(parent, [component])
                                folder.setData(0, Qt.UserRole+1, key)
                                folders[key] = folder
                            parent = folders[key]
                        title = relative.name+' · '+family
                    else:
                        title = labels.get(snapshot.path) or source.name
                    leaf = QTreeWidgetItem(parent, [title])
                    leaf.setData(0, Qt.UserRole, index)
                    leaf.setToolTip(0, (origin or {}).get('source', str(source))+'\n'+snapshot.path)
                    continue
                family_key = (root_key, family)
                families.setdefault(family_key,[]).append((index,snapshot,source))
            for (root_key,family),members in families.items():
                parent=roots[root_key]
                if grouping == "families":
                    parent=QTreeWidgetItem(parent,[f"{family} ({len(members)})"])
                    parent.setData(0,Qt.UserRole+1,root_key+'|'+family)
                for index,snapshot,source in members:
                    title=labels.get(snapshot.path) or source.name
                    leaf = QTreeWidgetItem(parent, [title])
                    leaf.setData(0, Qt.UserRole, index)
                    leaf.setToolTip(0, source.name+'\n'+snapshot.path)
            for item in self.items():
                if item.childCount():item.setExpanded(expanded.get(self.key(item), True))
            self.signature = signature
            self.filter()
        self.tree.blockSignals(True)
        for item in self.items():
            if item.data(0, Qt.UserRole) == active:
                self.tree.setCurrentItem(item)
        self.tree.blockSignals(False)

    def items(self):
        pending = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]
        while pending:
            item = pending.pop()
            yield item
            pending.extend(item.child(i) for i in range(item.childCount()))

    @staticmethod
    def key(item):
        return item.data(0, Qt.UserRole+1)

    def filter(self, *_):
        query = self.search.text().casefold().strip()
        def visit(item, parent_matches=False):
            matches = parent_matches or query in item.text(0).casefold()
            children = [visit(item.child(i), matches) for i in range(item.childCount())]
            visible = matches or any(children)
            item.setHidden(not visible)
            if query and children and visible:item.setExpanded(True)
            return visible
        for i in range(self.tree.topLevelItemCount()):visit(self.tree.topLevelItem(i))


def artifact_family(info, source):
    from fireblade.core.profiles import detect_profile
    profile = detect_profile(info.get('headers', []))
    if profile is not None:return profile.name
    import re
    stem = re.sub(r'^\d{8,14}[_ -]*', '', source.stem)
    for family, needles in [('Journaux Windows', ('evtx', 'eventlog')), ('Registre', ('registry', 'regcmd', 'system', 'software', 'ntuser')),
                            ('Système de fichiers', ('mft', 'usn', 'file', 'recycle')), ('Exécution', ('prefetch', 'amcache', 'shimcache', 'appcompat', 'pecmd')),
                            ('Navigateurs', ('webcache', 'chrome', 'firefox', 'history')), ('Journaux Linux', ('linux', 'syslog', 'auth.log', 'journal'))]:
        if any(word in stem.casefold() for word in needles):return family
    return stem or 'Autres artefacts'
