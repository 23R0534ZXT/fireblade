"""Collection import and offline detection controls."""

from collections import Counter
from datetime import datetime
from pathlib import Path
import uuid

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QPalette
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QRadioButton,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fireblade.core.collection import Collection, ToolPack
from fireblade.core.i18n import translate
from fireblade.ui.language import source_text
from fireblade.ui.alert_context import AlertContextMixin
from fireblade.ui.folder_picker import choose_import_sources
from fireblade.runtime.resources import resource_path
from fireblade.runtime.windows_paths import user_directory


class CollectionOrganizationDialog(QDialog):
    """Three layouts, named by what the analyst gets at the end.

    Two of them merge the files: one grid per artifact family (every EVTX together,
    every MFT together, every Amcache together) or one grid holding everything with a
    fixed grouping by family. The first one is what a streaming parse gives, and it is
    the only one that keeps the window usable while the folder is read.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Collection results")
        self.resize(680, 520)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        intro = QLabel(
            "Fireblade reads every file of the folder. Choose what you want on screen at the end."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        def option(radio, hint):
            layout.addWidget(radio)
            label = QLabel(hint)
            label.setWordWrap(True)
            label.setIndent(22)
            layout.addWidget(label)
            return label

        self.progressive = QRadioButton(
            "One grid per file — results appear as the folder is parsed"
        )
        self.progressive_hint = option(
            self.progressive,
            "Each analysed file opens in its own grid as it is read, and the window stays usable. "
            "A folder of a hundred EVTX files gives a hundred grids, listed one by one.",
        )
        self.artifacts = QRadioButton("One grid per artifact family — recommended")
        self.artifacts_hint = option(
            self.artifacts,
            "All EVTX in one grid, all MFT in another, all Amcache in another: one merged grid per "
            "family, with the source file kept as a column. The parse finishes before the grids open.",
        )
        self.combined = QRadioButton("One grid for everything, grouped by artifact family")
        self.combined_hint = option(
            self.combined,
            "A single grid holding every artifact, grouped by family. The grouping is fixed — it "
            "cannot be removed — and the columns of all sources are merged.",
        )
        self.artifacts.setChecked(True)

        self.layout_hint = QLabel(
            "The two merged layouts read every file first; the per-file grids are "
            "what you get while it parses."
        )
        self.layout_hint.setWordWrap(True)
        layout.addWidget(self.layout_hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Start parsing")
        buttons.button(QDialogButtonBox.Cancel).setText("Cancel")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def organization(self):
        if self.progressive.isChecked():
            return "files"
        return "combined" if self.combined.isChecked() else "artifacts"


class CollectionMixin(AlertContextMixin):
    def set_effort(self, level):
        """One slider for parsing and analysis, applied where they read settings."""
        from dataclasses import replace
        from fireblade.core.machine import effort
        from fireblade.core.preferences import save_preferences

        item = effort(level)
        previous = (
            self.preferences.effort_level,
            self.preferences.parsing_threads,
            self.preferences.query_threads,
            self.preferences.resource_memory_mb,
        )
        self.preferences.effort_level = level
        self.preferences.parsing_threads = item.threads
        self.preferences.query_threads = item.threads
        self.preferences.resource_memory_mb = item.memory_mb
        try:
            save_preferences(self.preferences)
        except (OSError, ValueError) as exc:
            (
                self.preferences.effort_level,
                self.preferences.parsing_threads,
                self.preferences.query_threads,
                self.preferences.resource_memory_mb,
            ) = previous
            self.effort_bar.set_level(previous[0], notify=False)
            self.error(exc)
            return
        self.settings = replace(self.settings, threads=item.threads, memory_mb=item.memory_mb)
        if self.collection is not None:
            self.collection.settings = self.settings
        if hasattr(self, "apply_resource_settings"):
            self.apply_resource_settings()

    def setup_collection(self):
        self.collection = None
        self._folder_queue = []
        from fireblade.ui.modular_workspace import Workbench

        self.workbench = Workbench(self)
        workspace = self.takeCentralWidget()
        workspace.setAutoFillBackground(True)
        workspace.setBackgroundRole(QPalette.Window)
        self.workbench.addTab(workspace, "Analyses")
        panel = QWidget()
        layout = QVBoxLayout(panel)
        title = QLabel("Imports")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        explanation = QLabel("Artefacts Windows, journaux Linux et collectes CatScale.")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        row = QHBoxLayout()
        for label, callback in [
            ("Import evidence…", self.parse_collection),
            ("Resume an import…", self.reopen_collection),
        ]:
            control = QPushButton(label)
            control.clicked.connect(callback)
            row.addWidget(control)
        layout.addLayout(row)
        from fireblade.ui.effort_bar import EffortBar

        self.effort_bar = EffortBar(getattr(self.preferences, "effort_level", "balanced"))
        self.effort_bar.chosen.connect(self.set_effort)
        layout.addWidget(self.effort_bar)
        self.detection_panel = QWidget()
        detection_layout = QVBoxLayout(self.detection_panel)
        detection_layout.addWidget(QLabel("Détection EVTX"))
        settings = QHBoxLayout()
        settings.addWidget(QLabel("Gravité minimale Hayabusa :"))
        self.hayabusa_level = QComboBox()
        for label, code in [
            ("Information", "informational"),
            (translate("Faible"), "low"),
            (translate("Moyenne"), "medium"),
            (translate("Élevée"), "high"),
            (translate("Critique"), "critical"),
        ]:
            self.hayabusa_level.addItem(label, code)
        self.hayabusa_level.setCurrentIndex(1)
        settings.addWidget(self.hayabusa_level)
        self.hayabusa_button = QPushButton("Analyser avec Hayabusa")
        self.hayabusa_button.clicked.connect(self.analyze_collection)
        settings.addWidget(self.hayabusa_button)
        settings.addStretch()
        detection_layout.addLayout(settings)
        self.hayabusa_hint = QLabel()
        self.hayabusa_hint.setTextFormat(Qt.PlainText)
        self.hayabusa_hint.setWordWrap(True)
        detection_layout.addWidget(self.hayabusa_hint)
        detection_layout.addStretch()
        from fireblade.ui.collection_report import CollectionReport

        self.collection_report = CollectionReport()
        self.collection_report.on_changed = self.save_collection_report
        self.collection_report.on_analyse = self.analyse_with_reader
        # The table follows the run instead of waiting for its end: it used to stay
        # empty while the counters advanced, which reads as 'nothing is happening'.
        self.report_timer = QTimer(self)
        self.report_timer.setInterval(1000)
        self.report_timer.timeout.connect(self.refresh_collection_report_live)
        layout.addWidget(self.collection_report, 1)
        self.workbench.addTab(panel, "Imports")
        self.setCentralWidget(self.workbench)
        file_menu = self.menuBar().actions()[0].menu()
        action = QAction("Import evidence…", self)
        action.triggered.connect(self.parse_collection)
        file_menu.insertAction(file_menu.actions()[1], action)
        analyze = self.hayabusa_action = QAction("Analyser la collecte avec Hayabusa", self)
        analyze.triggered.connect(self.analyze_collection)
        menu = next(
            a.menu()
            for a in self.menuBar().actions()
            if source_text(a).replace("&", "") == "Analyse"
        )
        menu.addAction(analyze)
        toolbar = self.collection_toolbar = self.addToolBar("Collecte")
        toolbar.addAction(action)
        # Detection belongs to the EVTX step, not the global file toolbar.
        help_menu = next(
            a.menu() for a in self.menuBar().actions() if a.text().replace("&", "") == "Aide"
        )
        sources = help_menu.addAction("Exporter les sources Hayabusa…")
        sources.triggered.connect(self.export_hayabusa_source)
        self.show_collection_report()
        self.setup_alert_context()

    def toolpack(self):
        return ToolPack(resource_path("forensic-tools"))

    def save_collection_report(self):
        """Persist the examiner's decisions with the collection they belong to."""
        collection = getattr(self, "collection", None)
        if collection is not None:
            collection.save()

    def collection_report_text(self, report=None):
        """The whole Imports report, in the text 'Full report' shows."""
        pack = self.toolpack()
        from fireblade.core.collection import PARSERS

        ready = [name for name in (*PARSERS, "Shellbags", "Hayabusa") if pack.available(name)]
        names = {
            "pending": "En attente",
            "running": "En cours",
            "complete": "Terminé",
            "complete_with_warnings": "Terminé avec avertissements",
            "unsupported": "Non reconnu",
            "skipped": "Ignoré",
            "error": "Erreur",
            "cancelled": "Interrompu",
            "attention": "À vérifier",
            "no_output": "Aucune sortie",
            "companion": "Journal de transaction",
        }
        # Every line is translated where it is written: the report is assembled after
        # the language pass, so a label cannot be translated as one block ("Full
        # report" showed the whole text in French under an English interface).
        status = lambda value: translate(names.get(value, value))
        lines = [
            translate(
                "Parsers intégrés : CatScale Linux, journaux /var/log/ et WebCache ESE (lecture seule)."
            ),
            translate("Moteurs Windows disponibles : {}").format(
                ", ".join(ready) or translate("aucun pack intégré dans cette construction")
            ),
        ]
        if report:
            organization = translate(
                {
                    "files": "Un onglet par résultat",
                    "artifacts": "Un onglet par artefact",
                    "combined": "Onglet unique regroupé par artefact",
                }.get(report.get("organization", "files"), "")
            )
            summary = report.get("summary") or {}
            counted = ", ".join(
                f"{status(key)} : {value}"
                for key, value in sorted(summary.items())
                if key not in ("files", "analyses")
            )
            lines += [
                "",
                translate("Organisation : {}").format(organization),
                translate("Dossier source : {}").format(report["source"]),
                translate("Dossier de travail : {}").format(report["output"]),
                translate("État de l’import : {}").format(status(report["status"])),
                translate("Bilan : {}").format(
                    str(dict(Counter(status(e["status"]) for e in report["files"])))
                ),
                translate("Analyses chargées : {}").format(len(report["documents"])),
                translate("Bilan par état : {}").format(counted),
                translate("Sources : {}").format(
                    " · ".join(report.get("sources") or [report.get("source", "")])
                ),
                translate("Journal de l’opération : {}").format(
                    Path(report.get("output", "")) / "journal.jsonl"
                ),
            ]
            for failure in report.get("organization_failures") or []:
                lines.append(
                    translate("{} : {}").format(
                        failure.get("artifact", ""), failure.get("reason", "")
                    )
                )
            verification = report.get("verification")
            if verification:
                lines += [
                    translate("Vérification des analyses : {} contrôlées · {} en échec").format(
                        verification.get("checked", 0), verification.get("broken", 0)
                    )
                ]
            if report.get("journal_error"):
                lines += [translate("Journal incomplet : {}").format(report["journal_error"])]
            if report.get("detection"):
                lines += [
                    translate("Hayabusa : {}").format(status(report["detection"]["status"])),
                    str(report["detection"].get("error", "")),
                ]
            for failure in report.get("organization_failures", []):
                lines += [
                    "Layout: "
                    + str(failure.get("artifact", ""))
                    + " not merged; results kept separate · "
                    + str(failure.get("reason", ""))[:300]
                ]
            for entry in report["files"]:
                lines.append(f"{status(entry['status'])} · {entry['path']}")
                if entry.get("sha256"):
                    lines.append("  SHA-256 : " + entry["sha256"])
                if entry.get("error"):
                    lines.append("  " + translate(entry["error"]))
                for run in entry.get("runs", []):
                    lines.append(
                        "  "
                        + run["tool"]
                        + " : "
                        + status(run["status"])
                        + " "
                        + translate(run.get("error", ""))
                    )
                    lines.extend(
                        "    " + translate(warning) for warning in run.get("warnings", [])[:10]
                    )
                    for member in run.get("linux_logs", run.get("catscale", {})).get("members", []):
                        if member["status"] in ("error", "unsupported", "skipped"):
                            lines.append(
                                "    "
                                + status(member["status"])
                                + " · "
                                + member["path"]
                                + " : "
                                + translate(member.get("reason", ""))
                            )
        lines += [
            "",
            translate(
                "Un fichier non reconnu, un moteur absent ou une erreur restent dans le bilan. Une alerte est une piste à vérifier, pas une conclusion de compromission. Les résultats et journaux sont conservés dans le dossier de travail."
            ),
        ]
        return "\n".join(lines)

    def show_collection_report(self, report=None):
        self.collection_report.set_report(report, self.collection_report_text(report))
        self.update_collection_controls()
        self.refresh_navigation()

    def refresh_collection_report_live(self):
        """Keep the Imports table in step with a collection that is still running."""
        report = getattr(getattr(self, "collection", None), "report", None)
        if not report:
            return
        self.collection_report.refresh(report, self.collection_report_text(report))

    def watch_collection_report(self, watching=True):
        timer = getattr(self, "report_timer", None)
        if timer is None:
            return
        timer.start() if watching else timer.stop()

    def update_collection_controls(self):
        if not hasattr(self, "hayabusa_action"):
            return
        report = self.collection.report if self.collection else None
        evtx = bool(
            report
            and any(
                "EvtxECmd" in e.get("tools", [])
                and (
                    e["status"] in ("complete", "complete_with_warnings")
                    or e["status"] == "attention"
                    and any(
                        run["tool"] == "EvtxECmd"
                        and run["status"] in ("complete", "complete_with_warnings")
                        and run.get("outputs")
                        for run in e.get("runs", [])
                    )
                )
                for e in report["files"]
            )
        )
        ready = (
            evtx
            and report["status"] not in ("pending", "running")
            and not self.busy
            and getattr(self, "disk_job", None) is None
        )
        self.hayabusa_action.setEnabled(ready)
        self.hayabusa_button.setEnabled(ready)
        self.hayabusa_level.setEnabled(ready)
        reason = (
            "Attendez la fin du traitement en cours."
            if self.busy
            else "Importez une collecte pour activer la détection."
            if report is None
            else "Hayabusa nécessite des EVTX parsés ; les textes CatScale se consultent dans Analyses."
            if not evtx
            else "EVTX disponibles. Choisissez le seuil puis lancez la détection."
        )
        detection = report.get("detection") if report else None
        if detection and detection.get("status") != "running":
            reason += (
                " Dernière détection : "
                + str(detection.get("alerts", 0))
                + " alerte(s) · "
                + str(detection["status"])
            )
        self.hayabusa_hint.setText(reason)
        self.hayabusa_action.setToolTip(reason)

    def collection_finished(self, report):
        self.watch_collection_report(False)
        self.coverage_panel.record_collection(report)
        self.show_collection_report(report)
        self.workbench.setCurrentIndex(1)
        if not report["documents"]:
            return
        collection = self.collection
        epoch = self._workspace_epoch
        self._collection_open_pending = True
        self.centralWidget().setEnabled(False)
        self.set_file_actions(False)

        def open_results():
            if self.pool.activeThreadCount():
                QTimer.singleShot(20, open_results)
                return
            try:
                if self.collection is not collection or self._workspace_epoch != epoch:
                    return
                from fireblade.core.sessions import read_session, write_session

                self.remember_active()
                if self.documents:
                    write_session(
                        collection.output / "previous-workspace.fireblade-session",
                        self.documents,
                        self.active_document,
                    )
                incoming, active = read_session(collection.output / "collection.fireblade-session")
                snapshots = incoming
                if getattr(self, "active_investigation", None) is not None:
                    existing = {snapshot.path for snapshot in self.documents}
                    # A merged layout replaces the per-file analyses it was built from. They
                    # were published while the parse streamed, and keeping them open is what
                    # showed a hundred EVTX grids next to the single one that was asked for.
                    replaced = {
                        str(item.get("path")) for item in (report.get("raw_documents") or [])
                    }
                    if replaced:
                        existing = {path for path in existing if path not in replaced}
                        snapshots = [
                            snapshot for snapshot in self.documents if snapshot.path in existing
                        ]
                    else:
                        snapshots = list(self.documents)
                    snapshots += [
                        snapshot for snapshot in incoming if snapshot.path not in existing
                    ]
                if len(snapshots) > 1000:
                    raise ValueError(
                        "Le case dépasserait 1000 analyses. Les résultats restent dans le dossier de collecte."
                    )
                wanted = (
                    getattr(self, "_reader_analysis", None)
                    or (report.get("detection") or {}).get("analysis")
                    or incoming[active].path
                )
                selected = next(
                    i for i, snapshot in enumerate(snapshots) if snapshot.path == wanted
                )
                self.validate_session_snapshots(snapshots)
                self.install_session_snapshots(snapshots, selected)
                self._reader_analysis = None
                if (report.get("detection") or {}).get("outputs"):
                    self.select_evidence_row(str(self.case.path), 1)
                self.workbench.setCurrentIndex(0)
                if getattr(self, "active_investigation", None) is not None:
                    self.remember_investigation_collection()
                    self.persist_investigation()
            except Exception as exc:
                self.error(exc)
            finally:
                self._collection_open_pending = False
                self.centralWidget().setEnabled(not self.busy)
                self.set_file_actions(self.model is not None and not self.busy)

        QTimer.singleShot(0, open_results)

    def start_collection_job(self, function):
        self.workbench.setCurrentIndex(1)

        def failed(message):
            self.watch_collection_report(False)
            self.show_collection_report(self.collection.report)
            self.collection_report.setPlainText(
                self.collection_report.toPlainText() + "\nErreur : " + message
            )
            self.workbench.setCurrentIndex(1)
            self.error(message)

        job = self.run(
            function,
            self.collection_finished,
            exclusive=True,
            on_error=failed,
            coverage_stage="Collecte",
        )
        if job is not None:
            self.collection.emit_text = job.signals.progress.emit
            self.watch_collection_report()
        self.cancel_action.setEnabled(True)

    def parse_collection(self):
        if not self.require_active_case():
            return
        if not self.can_open_file():
            return
        if (
            self.disk_job is not None
            or self.disk_pool.activeThreadCount()
            or self._disk_pending
            or self._folder_queue
        ):
            self.statusBar().showMessage(
                "Un import est déjà en cours. Attendez sa fin ou arrêtez-le."
            )
            return
        chosen = choose_import_sources(self)
        if not chosen:
            return
        try:
            paths = list(dict.fromkeys(str(Path(path).resolve(strict=True)) for path in chosen))
            if len(paths) > 1000:
                raise ValueError("Sélectionnez au plus 1000 sources.")
            missing = [path for path in paths if not Path(path).exists()]
            if missing:
                raise ValueError("Source introuvable : " + ", ".join(missing[:3]))
        except (OSError, ValueError) as exc:
            self.error(exc)
            return
        if len(paths) > 1 and self.active_investigation is None:
            self.error("Ouvrez un case pour importer plusieurs sources.")
            return
        dialog = CollectionOrganizationDialog(self)
        accepted = dialog.exec()
        organization = dialog.organization()
        dialog.deleteLater()
        if accepted != QDialog.DialogCode.Accepted:
            return
        # One operation, one report: the sources share a journal and a duplicate index,
        # so a file present in two of them is read once and named in the other row.
        self._folder_queue = [(paths, organization)]
        self.start_next_folder()

    def start_next_folder(self):
        if not self._folder_queue:
            return
        if (
            self.disk_job is not None
            or self.disk_pool.activeThreadCount()
            or not self.can_open_file()
        ):
            QTimer.singleShot(150, self.start_next_folder)
            return
        sources, organization = self._folder_queue.pop(0)
        parent = self.investigation_data_directory("Collectes") or user_directory() / "Collectes"
        parent.mkdir(parents=True, exist_ok=True)
        output = parent / (datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
        try:
            from dataclasses import replace

            # The collection gets the whole budget: halving it was what made a 3 GiB export
            # fail at 64 MB. An import that still runs out grows once instead of dying.
            settings = replace(
                self.settings,
                threads=self.preferences.parsing_threads,
                memory_mb=self.preferences.resource_memory_mb or self.settings.memory_mb,
            )
            collection = Collection(
                sources,
                output,
                self.toolpack(),
                settings,
                organization=organization,
                index_folder=parent,
            )
            if self.active_investigation is not None:
                collection.ready = self.disk_signals.documents.emit
                if self.start_background_collection(collection):
                    self.watch_collection_report()
                else:
                    self._folder_queue.clear()
            else:
                self.collection = collection
                self.start_collection_job(collection.parse)
        except (OSError, ValueError) as exc:
            self.error(exc)
            self._folder_queue.clear()

    def reopen_collection(self):
        if not self.can_open_file():
            return
        if self.disk_job is not None or self._folder_queue:
            self.statusBar().showMessage(
                "Attendez la fin de l’import avant de reprendre une autre collecte."
            )
            return
        path = QFileDialog.getExistingDirectory(
            self, "Dossier de travail contenant collection.json"
        )
        if not path:
            return
        if (
            getattr(self, "disk_job", None) is not None
            and Path(path).resolve() == self.disk_collection.output
        ):
            self.statusBar().showMessage("Cette collecte est encore en cours d’indexation.")
            return
        try:
            self.collection = Collection.reopen(
                path, self.toolpack(), self.settings, index_folder=Path(path).parent
            )
            remaining = self.collection.resumable()
            if remaining:
                # An operation that was stopped is not a collection to read: it is work
                # to finish, and the analyst decides whether to finish it now.
                answer = QMessageBox.question(
                    self,
                    translate("Resume import"),
                    translate(
                        "This import stopped with {} file(s) never read. Continue it now?"
                    ).format(remaining),
                )
                if answer == QMessageBox.Yes:
                    self.start_collection_job(self.collection.resume)
                    return
            self.collection_finished(self.collection.report)
        except Exception as exc:
            self.error(exc)

    def analyse_with_reader(self, path, reader):
        """Read one file with the reader the examiner picked, then show the analysis.

        A collection that could not identify a file is not the end of the story: the
        examiner can say what it is. The work happens on the collection's worker, so
        the window keeps drawing, and the new analysis is opened when it lands.
        """
        if self.collection is None:
            self.workbench.setCurrentIndex(1)
            self.statusBar().showMessage(
                "Importez ou reprenez une collecte avant de relancer un fichier."
            )
            return
        if not self.can_open_file():
            return
        self.remember_collection_views()

        def job():
            entry = self.collection.analyse_single(path, reader)
            outputs = (entry.get("runs") or [{}])[-1].get("outputs") or []
            self._reader_analysis = outputs[-1]["analysis"] if outputs else None
            return self.collection.report

        self.start_collection_job(job)

    def analyze_collection(self):
        if not self.can_open_file():
            return
        if self.collection is None:
            self.workbench.setCurrentIndex(1)
            self.statusBar().showMessage(
                "Importez ou reprenez une collecte avant l’analyse Hayabusa."
            )
            return
        if not any(
            "EvtxECmd" in entry.get("tools", []) for entry in self.collection.report["files"]
        ):
            self.workbench.setCurrentIndex(1)
            self.statusBar().showMessage(
                "Hayabusa nécessite des EVTX Windows. Les données CatScale se consultent dans les onglets d’analyse."
            )
            return
        self.remember_collection_views()
        level = self.hayabusa_level.currentData()
        self.start_collection_job(lambda: self.collection.analyze(level))

    def remember_collection_views(self):
        import base64
        import json

        self.remember_active()
        snapshots = {snapshot.path: snapshot for snapshot in self.documents}
        for document in self.collection.report["documents"]:
            snapshot = snapshots.get(document["path"])
            if snapshot is not None:
                document["view"] = json.loads(snapshot.view.to_json())
                document["header"] = base64.b64encode(snapshot.header_state).decode("ascii")
        self.collection.save()

    def export_hayabusa_source(self):
        import shutil

        source = resource_path("forensic-tools/Hayabusa-source.zip")
        if not source.is_file():
            self.error("Sources Hayabusa absentes de cette construction.")
            return
        target, _ = QFileDialog.getSaveFileName(
            self, "Exporter les sources Hayabusa", "Hayabusa-source.zip", "ZIP (*.zip)"
        )
        if target:
            if not self.export_destination_is_safe(target):
                return
            import os
            import tempfile

            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    dir=Path(target).parent, suffix=".partial", delete=False
                ) as stream:
                    temporary = Path(stream.name)
                shutil.copyfile(source, temporary)
                os.replace(temporary, target)
                self.statusBar().showMessage("Sources Hayabusa exportées : " + target)
            except OSError as exc:
                self.error(exc)
            finally:
                if temporary:
                    temporary.unlink(missing_ok=True)
