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
        from fireblade.core.paths import ensure_export_destination
        data = getattr(self, 'active_investigation', None)
        current = [collection for collection in (getattr(self,'collection',None),getattr(self,'disk_collection',None)) if collection]
        loaded = {str(collection.output.resolve()) for collection in current}
        directories = [entry['path'] for entry in getattr(self,'investigation_collections',[])
                       if str(Path(entry['path']).resolve()) not in loaded]
        try:
            ensure_export_destination(target, documents=self.documents, rule_path=self.rule_store.path,
                case_folder=self.investigation_library.folder(data['id']) if data else None,
                reports=[collection.report for collection in current], collection_directories=directories)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            self.error(str(exc))
            return False
        return True


    def integrity(self):
        if self.case and self.case.info:
            info = self.case.info
            QMessageBox.information(self, "Provenance de l’import", f"Source : {info['path']}\nOctets : {info['size']}\nLignes : {info['rows']}\nSHA-256 à l’import :\n{info['sha256']}\n\nLa source est lue sans modification. L’identifiant de ligne correspond à l’ordre des enregistrements CSV, hors en-tête (un enregistrement peut occuper plusieurs lignes physiques).")


