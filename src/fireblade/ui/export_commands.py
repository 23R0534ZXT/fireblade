"""Data/annotation export commands and destination protection."""
import copy
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox


class ExportCommandsMixin:
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
                 self.coverage_panel.export_done, exclusive=True,coverage_stage="Export",coverage_context=target)


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
        self.run(lambda: case.export(target, view, grouped, columns=columns), self.coverage_panel.export_done, exclusive=True,coverage_stage="Export",coverage_context=target)


    def export_destination_is_safe(self, target):
        protected = {Path(s.path).resolve() for s in self.documents} | {Path(s.source_info["path"]).resolve() for s in self.documents}
        protected.add(self.rule_store.path.resolve())
        data=getattr(self,'active_investigation',None)
        if data:
            folder=self.investigation_library.folder(data['id']);destination=Path(target).resolve()
            protected.update(folder/name for name in ('case.json','timeline-state.json','coverage-state.json','coverage-last.json'))
            if destination.is_relative_to(folder/'History') or destination.is_relative_to(folder/'IOC-hunts') or destination.parent==folder and destination.name.startswith('session-') and destination.suffix=='.fireblade-session':
                self.error('L’export ne peut pas remplacer les fichiers de sauvegarde et de couverture du case.');return False
        from fireblade.core.paths import protected_destination
        if protected_destination(target,protected):
            self.error("L’export ne peut pas écraser une source, une analyse ouverte ou les règles globales.")
            return False
        return True


    def integrity(self):
        if self.case and self.case.info:
            info = self.case.info
            QMessageBox.information(self, "Provenance de l’import", f"Source : {info['path']}\nOctets : {info['size']}\nLignes : {info['rows']}\nSHA-256 à l’import :\n{info['sha256']}\n\nLa source est lue sans modification. L’identifiant de ligne correspond à l’ordre des enregistrements CSV, hors en-tête (un enregistrement peut occuper plusieurs lignes physiques).")


