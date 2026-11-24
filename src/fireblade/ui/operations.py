"""The tracking tab: actions of a case (or of every case), its indicators and its machines.

The action table is the one the analyst asked for, in this order:

    Date · Priorité · État de l'action · Type d'action · Intervenant · Détails

When the scope is "all cases" a Case column is added on the left, because the same table
then mixes clients and an action without its case is unusable. Everything is stored in
``<case>/workspace.json`` through :mod:`fireblade.core.case_workspace`; this module only
collects, displays and hands edits to it.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from fireblade.core import case_workspace
from fireblade.core.i18n import translate
from fireblade.core.ioc_hunt import KINDS, read_indicator_file
from fireblade.core.model_texts import (
    ACTION_TYPE_LABELS,
    ENTITY_LABELS,
    IOC_STATUS_LABELS,
    OPEN_STATUSES,
    OWNER_LABELS,
    PRIORITY_LABELS,
    STATUS_LABELS,
)


ACTION_COLUMNS = ("Date", "Priorité", "État de l'action", "Type d'action", "Intervenant", "Détails")
IOC_COLUMNS = ("Type", "Valeur", "Statut", "Machine", "Libellé", "Source")
ENTITY_COLUMNS = ("Type", "Nom", "Hôte", "Adresse", "Système", "Étiquettes")


def _item(value, tooltip=None):
    item = QTableWidgetItem()
    item.setData(Qt.DisplayRole, "" if value is None else str(value))
    if tooltip:
        item.setToolTip(str(tooltip))
    return item


def _table(headers, widths=None):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(list(headers))
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setAlternatingRowColors(True)
    table.verticalHeader().hide()
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
    for index, width in enumerate(widths or ()):
        table.setColumnWidth(index, width)
    if widths:
        table.horizontalHeader().setSectionResizeMode(len(headers) - 1, QHeaderView.Stretch)
    return table


def parse_date(text):
    for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text.strip(), pattern).date()
        except (ValueError, AttributeError):
            continue
    return None


class ActionDialog(QDialog):
    """One action, in the six columns the tracking table shows and the fields behind them."""

    def __init__(self, parent=None, data=None, machines=()):
        super().__init__(parent)
        data = data or {}
        self.setWindowTitle("Modifier l'action" if data else "Nouvelle action")
        self.resize(620, 520)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd/MM/yyyy")
        existing = parse_date(data.get("date") or "")
        self.date.setDate(
            QDate(existing.year, existing.month, existing.day) if existing else QDate.currentDate()
        )
        form.addRow("Date :", self.date)
        self.priority = QComboBox()
        for code, label in PRIORITY_LABELS.items():
            self.priority.addItem(label, code)
        self.priority.setCurrentIndex(
            max(0, self.priority.findData(data.get("priority", "medium")))
        )
        form.addRow("Priorité :", self.priority)
        self.status = QComboBox()
        for code, label in STATUS_LABELS.items():
            self.status.addItem(label, code)
        self.status.setCurrentIndex(max(0, self.status.findData(data.get("status", "todo"))))
        form.addRow("État de l'action :", self.status)
        self.type = QComboBox()
        for code, label in ACTION_TYPE_LABELS.items():
            self.type.addItem(label, code)
        self.type.setCurrentIndex(max(0, self.type.findData(data.get("type", "other"))))
        form.addRow("Type d'action :", self.type)
        self.intervenant = QLineEdit(data.get("intervenant", ""))
        self.intervenant.setPlaceholderText("Nom ou équipe qui porte l'action")
        form.addRow("Intervenant :", self.intervenant)
        self.machine = QComboBox()
        self.machine.setEditable(True)
        self.machine.addItem("")
        for label in machines:
            self.machine.addItem(label)
        self.machine.setCurrentText(data.get("machine", ""))
        form.addRow("Machine / compte :", self.machine)
        self.reference = QLineEdit(data.get("reference", ""))
        self.reference.setPlaceholderText("Ticket, courriel, référence client…")
        form.addRow("Référence :", self.reference)
        layout.addLayout(form)
        layout.addWidget(QLabel("Détails :"))
        self.details = QPlainTextEdit()
        text = data.get("detail") or ""
        if data.get("title"):
            text = data["title"] + ("\n" + text if text else "")
        self.details.setPlainText(text)
        self.details.setPlaceholderText(
            "Ce qui doit être fait, par qui, avec quel résultat attendu…"
        )
        layout.addWidget(self.details, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Enregistrer")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        text = self.details.toPlainText().strip()
        title = text.splitlines()[0].strip() if text else ""
        detail = "\n".join(text.splitlines()[1:]).strip() if text else ""
        if not title:
            title = "(action sans intitulé)"
        return dict(
            title=title[:200],
            detail=detail[:8000],
            date=self.date.date().toString("yyyy-MM-dd"),
            priority=self.priority.currentData(),
            status=self.status.currentData(),
            type=self.type.currentData(),
            intervenant=self.intervenant.text().strip()[:200],
            machine=self.machine.currentText().strip()[:200],
            reference=self.reference.text().strip()[:120],
        )


class ClientDialog(QDialog):
    def __init__(self, parent=None, workspace=None):
        super().__init__(parent)
        workspace = workspace or {}
        client = workspace.get("client") or {}
        engagement = workspace.get("engagement") or {}
        self.setWindowTitle("Client et mission")
        self.resize(560, 480)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(client.get("name", ""))
        self.reference = QLineEdit(client.get("reference", ""))
        self.sector = QLineEdit(client.get("sector", ""))
        self.contact = QLineEdit(client.get("contact", ""))
        self.contract = QLineEdit(engagement.get("contract", ""))
        self.lead = QLineEdit(engagement.get("lead", ""))
        self.start = QLineEdit(engagement.get("start") or "")
        self.end = QLineEdit(engagement.get("end") or "")
        self.start.setPlaceholderText("AAAA-MM-JJ")
        self.end.setPlaceholderText("AAAA-MM-JJ")
        self.notes = QPlainTextEdit(engagement.get("notes", ""))
        self.notes.setMaximumHeight(140)
        for label, widget in (
            ("Client :", self.name),
            ("Référence dossier :", self.reference),
            ("Secteur :", self.sector),
            ("Contact client :", self.contact),
            ("Contrat :", self.contract),
            ("Responsable de mission :", self.lead),
            ("Début :", self.start),
            ("Fin :", self.end),
        ):
            form.addRow(label, widget)
        layout.addLayout(form)
        layout.addWidget(QLabel("Périmètre et notes de mission :"))
        layout.addWidget(self.notes)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        return dict(
            client=dict(
                name=self.name.text().strip(),
                reference=self.reference.text().strip(),
                sector=self.sector.text().strip(),
                contact=self.contact.text().strip(),
            ),
            engagement=dict(
                contract=self.contract.text().strip(),
                lead=self.lead.text().strip(),
                start=self.start.text().strip() or None,
                end=self.end.text().strip() or None,
                notes=self.notes.toPlainText().strip(),
            ),
        )


class IocDialog(QDialog):
    def __init__(self, parent=None, machines=()):
        super().__init__(parent)
        self.setWindowTitle("Ajouter un indicateur")
        self.resize(520, 280)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.value = QLineEdit()
        self.value.setPlaceholderText("domaine, IP, URL ou empreinte")
        self.kind = QComboBox()
        self.kind.addItem("Détection automatique", "")
        for code, label in KINDS.items():
            self.kind.addItem(label, code)
        self.label = QLineEdit()
        self.status = QComboBox()
        for code, label in IOC_STATUS_LABELS.items():
            self.status.addItem(label, code)
        self.machine = QComboBox()
        self.machine.setEditable(True)
        self.machine.addItem("")
        for name in machines:
            self.machine.addItem(name)
        self.source = QLineEdit()
        self.source.setPlaceholderText("rapport, client, analyse…")
        for label, widget in (
            ("Valeur :", self.value),
            ("Type :", self.kind),
            ("Libellé :", self.label),
            ("Statut :", self.status),
            ("Machine :", self.machine),
            ("Source :", self.source),
        ):
            form.addRow(label, widget)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        return dict(
            value=self.value.text().strip(),
            kind=self.kind.currentData(),
            label=self.label.text().strip(),
            status=self.status.currentData(),
            machine=self.machine.currentText().strip(),
            source=self.source.text().strip(),
        )


class EntityDialog(QDialog):
    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        data = data or {}
        self.setWindowTitle("Machine ou compte")
        self.resize(500, 320)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.kind = QComboBox()
        for code, label in ENTITY_LABELS.items():
            self.kind.addItem(label, code)
        self.kind.setCurrentIndex(max(0, self.kind.findData(data.get("kind", "machine"))))
        self.label = QLineEdit(data.get("label", ""))
        self.hostname = QLineEdit(data.get("hostname", ""))
        self.ip = QLineEdit(data.get("ip", ""))
        self.os = QLineEdit(data.get("os", ""))
        self.tags = QLineEdit(", ".join(data.get("tags") or []))
        self.notes = QPlainTextEdit(data.get("notes", ""))
        self.notes.setMaximumHeight(100)
        for label, widget in (
            ("Type :", self.kind),
            ("Nom :", self.label),
            ("Hôte :", self.hostname),
            ("Adresse :", self.ip),
            ("Système :", self.os),
            ("Étiquettes (séparées par des virgules) :", self.tags),
        ):
            form.addRow(label, widget)
        layout.addLayout(form)
        layout.addWidget(QLabel("Notes :"))
        layout.addWidget(self.notes)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        return dict(
            kind=self.kind.currentData(),
            label=self.label.text().strip(),
            hostname=self.hostname.text().strip(),
            ip=self.ip.text().strip(),
            os=self.os.text().strip(),
            notes=self.notes.toPlainText().strip(),
            tags=[tag.strip() for tag in self.tags.text().split(",") if tag.strip()],
        )


class OperationsPanel(QWidget):
    """Actions, indicators and machines, for the active case or for all of them."""

    changed = Signal()

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.workspace = None
        self._workspace_error = ""
        self.case_workspaces = {}
        self._build()

    # ------------------------------------------------------------------ helpers
    def case_folder(self, identifier):
        return self.window.investigation_library.folder(identifier)

    def active_case(self):
        return getattr(self.window, "active_investigation", None)

    def scope_all(self):
        return self.scope.currentData() == "all"

    def load_workspace(self):
        """Read the active case's workspace, or every case's when the board is global."""
        if self.scope_all():
            board, errors = case_workspace.collect(self.window.investigation_library.root)
            self.case_workspaces = {item["case"]: item for item in board}
            self.workspace = None
            if errors:
                self.status.setText("Cases illisibles : " + " ; ".join(errors[:3]))
            return
        case = self.active_case()
        if case is None:
            self.workspace = None
            return
        self._workspace_error = ""
        try:
            self.workspace = case_workspace.load(self.case_folder(case["id"]))
        except (OSError, ValueError) as exc:
            # A corrupt workspace must not open a modal on every case switch: the panel
            # says it once, keeps working and lets the analyst repair the file.
            self.workspace = None
            self._workspace_error = translate("Case workspace illisible : {}").format(str(exc))

    def machines(self):
        names = []
        for item in (self.workspace or {}).get("entities") or []:
            names.append(item.get("label") or item.get("hostname") or "")
        for item in self.window.documents:
            # Older documents are snapshots with attributes, newer ones mappings.
            navigation = (
                item.get("navigation")
                if isinstance(item, dict)
                else getattr(item, "navigation", None)
            )
            for key in ("machine", "host"):
                if isinstance(navigation, dict) and navigation.get(key):
                    names.append(str(navigation[key]))
        return sorted({name for name in names if name})

    # ----------------------------------------------------------------- interface
    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 6)
        title = QLabel("Actions et suivi")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        hint = QLabel(
            "Une action par ligne. La date, la priorité, l'état, le type, l'intervenant et "
            "les détails sont enregistrés dans le case ; le tableau peut couvrir tous les cases."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        bar = QHBoxLayout()
        self.scope = QComboBox()
        self.scope.addItem("Case courant", "case")
        self.scope.addItem("Tous les cases", "all")
        self.scope.currentIndexChanged.connect(self.refresh)
        bar.addWidget(QLabel("Périmètre :"))
        bar.addWidget(self.scope)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher dans les détails, l'intervenant, la machine…")
        self.search.textChanged.connect(lambda *_: self.refresh(reload=False))
        bar.addWidget(self.search, 1)
        self.open_only = QCheckBox("Actions ouvertes seulement")
        self.open_only.toggled.connect(lambda *_: self.refresh(reload=False))
        bar.addWidget(self.open_only)
        refresh = QPushButton("Actualiser")
        refresh.clicked.connect(self.refresh)
        bar.addWidget(refresh)
        layout.addLayout(bar)
        bar2 = QHBoxLayout()
        for label, callback in (
            ("Nouvelle action…", self.add_action),
            ("Modifier…", self.edit_action),
            ("Supprimer", self.remove_action),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            bar2.addWidget(button)
            if label == "Nouvelle action…":
                self.add_button = button
            if label == "Modifier…":
                self.edit_button = button
            if label == "Supprimer":
                self.remove_button = button
        # Secondary commands live behind one button: five visible labels would make this
        # tab the widest widget of the window and stop Fireblade fitting a 1024 screen.
        more = QToolButton()
        more.setText("⋯")
        more.setToolTip("Client, mission et export du suivi")
        menu = QMenu(more)
        menu.addAction("Client et mission…", self.edit_client)
        menu.addAction("Exporter le suivi…", self.export_tracking)
        more.setMenu(menu)
        more.setPopupMode(QToolButton.InstantPopup)
        bar2.addWidget(more)
        bar2.addStretch()
        layout.addLayout(bar2)
        self.tabs = QTabWidget()
        self.actions_table = _table(ACTION_COLUMNS, (95, 85, 140, 130, 150, 420))
        self.actions_table.doubleClicked.connect(lambda *_: self.edit_action())
        self.actions_table.setContextMenuPolicy(Qt.ActionsContextMenu)
        for label, callback in (
            ("Marquer terminée", self.complete_action),
            ("Rouvrir", self.reopen_action),
            ("Supprimer", self.remove_action),
        ):
            action = QAction(label, self)
            action.triggered.connect(callback)
            self.actions_table.addAction(action)
        self.tabs.addTab(self.actions_table, "Actions")
        self.ioc_table = _table(IOC_COLUMNS, (90, 260, 110, 150, 200, 160))
        self.tabs.addTab(self.ioc_table, "Indicateurs")
        self.entity_table = _table(ENTITY_COLUMNS, (90, 170, 150, 130, 150, 200))
        self.tabs.addTab(self.entity_table, "Machines et comptes")
        layout.addWidget(self.tabs, 1)
        ioc_bar = QHBoxLayout()
        self.ioc_value = QLineEdit()
        self.ioc_value.setPlaceholderText("Valeur de l'indicateur (le type est déduit)")
        ioc_bar.addWidget(self.ioc_value, 2)
        add_ioc = QPushButton("Ajouter…")
        add_ioc.clicked.connect(self.add_indicator)
        ioc_bar.addWidget(add_ioc)
        ioc_menu = QMenu(self)
        ioc_menu.addAction("Importer une liste…", self.import_indicators)
        ioc_menu.addAction("Retirer", self.remove_indicator)
        ioc_more = QToolButton()
        ioc_more.setText("⋯")
        ioc_more.setMenu(ioc_menu)
        ioc_more.setPopupMode(QToolButton.InstantPopup)
        ioc_bar.addWidget(ioc_more)
        self.ioc_bar = QWidget()
        self.ioc_bar.setLayout(ioc_bar)
        layout.addWidget(self.ioc_bar)
        entity_bar = QHBoxLayout()
        add_entity = QPushButton("Ajouter…")
        add_entity.setToolTip("Ajouter une machine ou un compte…")
        add_entity.clicked.connect(self.add_entity)
        entity_bar.addWidget(add_entity)
        entity_menu = QMenu(self)
        entity_menu.addAction("Modifier…", self.edit_entity)
        entity_menu.addAction("Retirer", self.remove_entity)
        entity_more = QToolButton()
        entity_more.setText("⋯")
        entity_more.setMenu(entity_menu)
        entity_more.setPopupMode(QToolButton.InstantPopup)
        entity_bar.addWidget(entity_more)
        entity_bar.addStretch()
        self.entity_bar = QWidget()
        self.entity_bar.setLayout(entity_bar)
        layout.addWidget(self.entity_bar)
        self.ioc_bar.setVisible(False)
        self.entity_bar.setVisible(False)
        self.tabs.currentChanged.connect(self.tab_changed)
        self.status = QLabel()
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.notice = QLabel()
        self.notice.setTextFormat(Qt.PlainText)
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        self.actions_table.itemSelectionChanged.connect(self.selection_changed)
        self.refresh()

    def tab_changed(self, index):
        self.ioc_bar.setVisible(index == 1)
        self.entity_bar.setVisible(index == 2)

    def refresh(self, reload=True):
        if reload:
            self.load_workspace()
        self.fill_actions()
        self.fill_iocs()
        self.fill_entities()
        self.update_buttons()

    def update_buttons(self):
        enabled = self.active_case() is not None and not self.scope_all()
        for button in (self.add_button, self.edit_button, self.remove_button):
            button.setEnabled(enabled)
        self.add_button.setToolTip(
            "" if enabled else "Choisissez un case actif pour y ajouter une action."
        )

    def rows(self):
        """(case id, case name, workspace, client name) for the selected scope."""
        if self.scope_all():
            result = []
            for identifier, item in sorted(
                self.case_workspaces.items(), key=lambda pair: pair[1].get("name", "")
            ):
                workspace = item.get("workspace") or {}
                result.append(
                    (
                        identifier,
                        item.get("name", ""),
                        item.get("workspace"),
                        (workspace.get("client") or {}).get("name", ""),
                    )
                )
            return result
        case = self.active_case()
        if case is None or self.workspace is None:
            return []
        return [
            (
                case["id"],
                case["name"],
                self.workspace,
                (self.workspace.get("client") or {}).get("name", ""),
            )
        ]

    def fill_actions(self):
        query = self.search.text().strip().casefold()
        open_only = self.open_only.isChecked()
        rows = []
        for identifier, name, workspace, client_name in self.rows():
            if workspace is None:
                continue
            for item in workspace.get("actions") or []:
                if open_only and item.get("status") not in OPEN_STATUSES:
                    continue
                haystack = " ".join(
                    str(item.get(key, ""))
                    for key in ("title", "detail", "intervenant", "machine", "reference")
                ).casefold()
                if query and query not in haystack:
                    continue
                rows.append((identifier, name, item, client_name))
        rows.sort(
            key=lambda row: (
                row[2].get("status") in ("done", "cancelled"),
                row[2].get("date") or "9999",
                row[2].get("priority") or "",
            )
        )
        self.action_rows = rows
        all_cases = self.scope_all()
        headers = (("Case", "Client") + ACTION_COLUMNS) if all_cases else ACTION_COLUMNS
        self.actions_table.blockSignals(True)
        self.actions_table.setColumnCount(len(headers))
        self.actions_table.setHorizontalHeaderLabels(list(headers))
        self.actions_table.setRowCount(len(rows))
        offset = 2 if all_cases else 0
        for row, (identifier, name, item, client_name) in enumerate(rows):
            if all_cases:
                self.actions_table.setItem(row, 0, _item(name))
                self.actions_table.setItem(row, 1, _item(client_name or "—"))
            details = item.get("title", "")
            if item.get("detail"):
                details += " — " + " ".join(item["detail"].split())
            values = (
                item.get("date", ""),
                translate(PRIORITY_LABELS.get(item.get("priority"), "")),
                translate(STATUS_LABELS.get(item.get("status"), "")),
                translate(ACTION_TYPE_LABELS.get(item.get("type"), "")),
                item.get("intervenant") or translate(OWNER_LABELS.get(item.get("owner"), "")),
                details,
            )
            for column, value in enumerate(values):
                cell = _item(value, details if column == 5 else None)
                if column == 2 and item.get("status") in ("done", "cancelled"):
                    font = cell.font()
                    font.setStrikeOut(True)
                    cell.setFont(font)
                self.actions_table.setItem(row, offset + column, cell)
        if all_cases:
            self.actions_table.setColumnWidth(0, 170)
            self.actions_table.setColumnWidth(1, 150)
        self.actions_table.blockSignals(False)
        open_count = sum(1 for _i, _n, item, _c in rows if item.get("status") in OPEN_STATUSES)
        overdue = sum(
            1
            for _i, _n, item, _c in rows
            if item.get("due")
            and item.get("status") in OPEN_STATUSES
            and str(item["due"]) < date.today().isoformat()
        )
        scope_label = "tous les cases" if all_cases else _one_case_label(self)
        summary = (
            f"{len(rows)} action(s) · {open_count} ouverte(s) · {overdue} en retard · {scope_label}"
        )
        if not rows:
            summary += " · " + translate("Aucune action enregistrée dans ce périmètre.")
        if getattr(self, "_workspace_error", ""):
            summary = self._workspace_error + " · " + summary
        self.status.setText(summary)
        self.notice.clear()

    def fill_iocs(self):
        rows = []
        for identifier, name, workspace, _client in self.rows():
            if workspace is None:
                continue
            for item in workspace.get("iocs") or []:
                rows.append((identifier, name, item))
        self.ioc_rows = rows
        self.ioc_table.setRowCount(len(rows))
        for row, (_identifier, _name, item) in enumerate(rows):
            values = (
                translate(KINDS.get(item.get("kind"), item.get("kind"))),
                item.get("value"),
                translate(IOC_STATUS_LABELS.get(item.get("status"), item.get("status"))),
                item.get("machine", ""),
                item.get("label", ""),
                item.get("source", ""),
            )
            for column, value in enumerate(values):
                self.ioc_table.setItem(row, column, _item(value))

    def fill_entities(self):
        rows = []
        for identifier, name, workspace, _client in self.rows():
            if workspace is None:
                continue
            for item in workspace.get("entities") or []:
                rows.append((identifier, name, item))
        self.entity_rows = rows
        self.entity_table.setRowCount(len(rows))
        for row, (_identifier, _name, item) in enumerate(rows):
            values = (
                translate(ENTITY_LABELS.get(item.get("kind"), item.get("kind"))),
                item.get("label"),
                item.get("hostname", ""),
                item.get("ip", ""),
                item.get("os", ""),
                ", ".join(item.get("tags") or []),
            )
            for column, value in enumerate(values):
                self.entity_table.setItem(row, column, _item(value))

    def selection_changed(self):
        pass

    def export_tracking(self):
        """The table as a file, for the client or for another tool."""
        import csv
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter le suivi des actions", "suivi-actions.csv", "CSV (*.csv)"
        )
        if not path:
            return
        if not path.casefold().endswith(".csv"):
            path += ".csv"
        all_cases = self.scope_all()
        headers = (
            (["Case", "Client"] if all_cases else [])
            + list(ACTION_COLUMNS)
            + ["Machine", "Référence", "Échéance"]
        )
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream, delimiter=";")
                writer.writerow(headers)
                for identifier, name, item, client_name in self.action_rows:
                    row = ([name, client_name or ""] if all_cases else []) + [
                        item.get("date", ""),
                        translate(PRIORITY_LABELS.get(item.get("priority"), "")),
                        translate(STATUS_LABELS.get(item.get("status"), "")),
                        translate(ACTION_TYPE_LABELS.get(item.get("type"), "")),
                        item.get("intervenant")
                        or translate(OWNER_LABELS.get(item.get("owner"), "")),
                        item.get("title", " ")[:200] if item.get("title") else "",
                    ]
                    if item.get("detail"):
                        row[-1] += " — " + " ".join(item["detail"].split())
                    row += [
                        item.get("machine", ""),
                        item.get("reference", ""),
                        item.get("due") or "",
                    ]
                    writer.writerow(row)
        except OSError as exc:
            self.window.error(str(exc))
            return
        self.notice.setText("Suivi exporté : " + path)

    # ------------------------------------------------------------------- actions
    def selected_action(self):
        row = self.actions_table.currentRow()
        if row < 0 or row >= len(getattr(self, "action_rows", [])):
            return None
        identifier, _name, item, _client = self.action_rows[row]
        return identifier, item

    def require_case(self):
        case = self.active_case()
        if case is None:
            self.window.error("Ouvrez un case avant d'enregistrer une action.")
            return None
        if self.scope_all():
            self.window.error("Choisissez le périmètre « Case courant » pour modifier une action.")
            return None
        return case

    def add_action(self):
        case = self.require_case()
        if case is None:
            return
        dialog = ActionDialog(self, machines=self.machines())
        try:
            if dialog.exec() != QDialog.Accepted:
                return
            values = dialog.values()
            values["case"] = case["id"]
            case_workspace.add_action(self.case_folder(case["id"]), values.pop("title"), **values)
            self.refresh()
            self.changed.emit()
        except (OSError, ValueError) as exc:
            self.window.error(str(exc))
        finally:
            dialog.deleteLater()

    def edit_action(self):
        selected = self.selected_action()
        if selected is None:
            return
        identifier, item = selected
        case = self.require_case()
        if case is None:
            return
        dialog = ActionDialog(self, data=item, machines=self.machines())
        try:
            if dialog.exec() != QDialog.Accepted:
                return
            case_workspace.update_action(
                self.case_folder(case["id"]), item["id"], **dialog.values()
            )
            self.refresh()
            self.changed.emit()
        except (OSError, ValueError) as exc:
            self.window.error(str(exc))
        finally:
            dialog.deleteLater()

    def remove_action(self):
        selected = self.selected_action()
        case = self.require_case()
        if selected is None or case is None:
            return
        if (
            QMessageBox.question(
                self, "Supprimer l'action", "Supprimer définitivement cette action du case ?"
            )
            != QMessageBox.Yes
        ):
            return
        try:
            case_workspace.remove_action(self.case_folder(case["id"]), selected[1]["id"])
            self.refresh()
            self.changed.emit()
        except (OSError, ValueError) as exc:
            self.window.error(str(exc))

    def set_status(self, status):
        selected = self.selected_action()
        case = self.require_case()
        if selected is None or case is None:
            return
        try:
            case_workspace.update_action(
                self.case_folder(case["id"]), selected[1]["id"], status=status
            )
            self.refresh()
            self.changed.emit()
        except (OSError, ValueError) as exc:
            self.window.error(str(exc))

    def complete_action(self):
        self.set_status("done")

    def reopen_action(self):
        self.set_status("in_progress")

    def edit_client(self):
        case = self.require_case()
        if case is None:
            return
        folder = self.case_folder(case["id"])
        try:
            workspace = case_workspace.load(folder)
        except (OSError, ValueError) as exc:
            self.window.error(str(exc))
            return
        dialog = ClientDialog(self, workspace)
        try:
            if dialog.exec() != QDialog.Accepted:
                return
            values = dialog.values()
            workspace.update(values)
            case_workspace.save(folder, workspace)
            self.refresh()
            self.changed.emit()
        except (OSError, ValueError) as exc:
            self.window.error(str(exc))
        finally:
            dialog.deleteLater()

    # --------------------------------------------------------------- indicators
    def add_indicator(self):
        case = self.require_case()
        if case is None:
            return
        dialog = IocDialog(self, machines=self.machines())
        if self.ioc_value.text().strip():
            dialog.value.setText(self.ioc_value.text().strip())
        try:
            if dialog.exec() != QDialog.Accepted:
                return
            values = dialog.values()
            raw = values.pop("value")
            values["case"] = case["id"]
            case_workspace.add_ioc(
                self.case_folder(case["id"]), raw, values.pop("kind") or None, **values
            )
            self.ioc_value.clear()
            self.refresh()
            self.changed.emit()
        except (OSError, ValueError) as exc:
            self.window.error(str(exc))
        finally:
            dialog.deleteLater()

    def import_indicators(self):
        case = self.require_case()
        if case is None:
            return
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Importer une liste d'indicateurs",
            "",
            "Listes (*.txt *.csv *.tsv);;Tous les fichiers (*)",
        )
        if not path:
            return
        try:
            batch = read_indicator_file(path)
        except (OSError, ValueError) as exc:
            self.window.error(str(exc))
            return
        folder = self.case_folder(case["id"])
        try:
            result = case_workspace.add_iocs(
                folder,
                [ioc.raw for ioc in batch.indicators],
                source=Path(path).name[:200],
                case=case["id"],
            )
        except (OSError, ValueError) as exc:
            self.window.error(str(exc))
            return
        self.refresh()
        self.changed.emit()
        self.notice.setText(
            f"{result['added']} indicateur(s) ajouté(s), {result['skipped']} doublon(s) "
            f"ou invalide(s), {len(batch.rejected)} ligne(s) rejetée(s)."
        )

    def selected_indicator(self):
        row = self.ioc_table.currentRow()
        if row < 0 or row >= len(getattr(self, "ioc_rows", [])):
            return None
        return self.ioc_rows[row]

    def remove_indicator(self):
        selected = self.selected_indicator()
        case = self.require_case()
        if selected is None or case is None:
            return
        try:
            case_workspace.remove_ioc(self.case_folder(selected[0]), selected[2]["id"])
            self.refresh()
            self.changed.emit()
        except (OSError, ValueError) as exc:
            self.window.error(str(exc))

    # ---------------------------------------------------------------- entities
    def selected_entity(self):
        row = self.entity_table.currentRow()
        if row < 0 or row >= len(getattr(self, "entity_rows", [])):
            return None
        return self.entity_rows[row]

    def add_entity(self):
        case = self.require_case()
        if case is None:
            return
        dialog = EntityDialog(self)
        try:
            if dialog.exec() != QDialog.Accepted:
                return
            values = dialog.values()
            case_workspace.add_entity(
                self.case_folder(case["id"]), values.pop("kind"), values.pop("label"), **values
            )
            self.refresh()
            self.changed.emit()
        except (OSError, ValueError) as exc:
            self.window.error(str(exc))
        finally:
            dialog.deleteLater()

    def edit_entity(self):
        selected = self.selected_entity()
        case = self.require_case()
        if selected is None or case is None:
            return
        identifier, _name, entity = selected
        dialog = EntityDialog(self, entity)
        try:
            if dialog.exec() != QDialog.Accepted:
                return
            values = dialog.values()
            folder = self.case_folder(identifier)

            def change(data):
                target = next(
                    (item for item in data["entities"] if item["id"] == entity["id"]), None
                )
                if target is None:
                    raise ValueError("Cette machine n'existe plus dans le case.")
                target.update(values)

            case_workspace.mutate(folder, change)
            self.refresh()
            self.changed.emit()
        except (OSError, ValueError) as exc:
            self.window.error(str(exc))
        finally:
            dialog.deleteLater()

    def remove_entity(self):
        selected = self.selected_entity()
        if selected is None:
            return
        identifier, _name, entity = selected
        if (
            QMessageBox.question(
                self, "Retirer la machine", "Retirer cette machine ou ce compte du case ?"
            )
            != QMessageBox.Yes
        ):
            return
        try:

            def change(data):
                before = len(data["entities"])
                data["entities"][:] = [
                    item for item in data["entities"] if item["id"] != entity["id"]
                ]
                if len(data["entities"]) == before:
                    raise ValueError("Cette machine n'existe plus dans le case.")

            case_workspace.mutate(self.case_folder(identifier), change)
            self.refresh()
            self.changed.emit()
        except (OSError, ValueError) as exc:
            self.window.error(str(exc))


def _one_case_label(panel):
    case = panel.active_case()
    return case["name"] if case else translate("aucun case actif")
