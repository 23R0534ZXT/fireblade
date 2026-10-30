"""Window commands for global rules; persistence and matching stay independent."""
from pathlib import Path

from PySide6.QtWidgets import QFileDialog

from .advanced_dialogs import RulesDialog
from .rule_store import RuleBook, RuleStore, atomic_write, read_book
from .windows_paths import user_directory


class SharedRulesMixin:
    def setup_shared_rules(self, path=None):
        self.rule_store = RuleStore(path if path is not None else user_directory() / "regles-globales.json")
        self.rule_book, self.global_rules_error = RuleBook(), None
        self.reload_global_rules()

    def reload_global_rules(self):
        try:
            self.rule_book = self.rule_store.load()
            self.global_rules_error = None
        except Exception as exc:
            self.rule_book = RuleBook()
            self.global_rules_error = str(exc)
            self.statusBar().showMessage("Règles globales illisibles : l’analyse reste disponible")
        if self.case:
            self.apply()
        else:
            self.global_rules_for_view()

    def global_rules_for_view(self):
        if self.global_rules_error:
            self.rules_summary.setText("Règles globales : fichier invalide")
            self.rules_summary.setToolTip(f"{self.rule_store.path}\n{self.global_rules_error}\nImporter un fichier valide ou corriger puis recharger.")
            return []
        if not self.case:
            self.rules_summary.clear()
            return []
        if not self.view.global_rules_enabled:
            self.rules_summary.setText("Règles globales : désactivées")
            self.rules_summary.setToolTip("Désactivées pour cette vue uniquement")
            return []
        rules, skipped = self.rule_book.adapt(self.case.headers)
        active = sum(rule.enabled for rule in rules)
        self.rules_summary.setText(f"Règles globales : {active} active(s)" + (f", {len(skipped)} non applicable(s)" if skipped else "") if self.rule_book.rules else "")
        self.rules_summary.setToolTip("\n".join(skipped) if skipped else str(self.rule_store.path))
        return rules

    def toggle_global_rules(self, enabled):
        if self.case and not self.busy:
            self.view.global_rules_enabled = enabled
            self.apply()

    def edit_global_rules(self):
        if self.busy:
            return
        if self.global_rules_error:
            self.error(f"Le fichier {self.rule_store.path} est invalide :\n{self.global_rules_error}\nCorrigez-le ou importez un fichier de règles valide.")
            return
        book = self.rule_book.with_columns(self.case.headers if self.case else [])
        if not book.headers:
            self.statusBar().showMessage("Ouvrez une analyse pour proposer ses noms de colonnes")
            return
        dialog = RulesDialog(book.headers, book.rules, self)
        dialog.setWindowTitle("Règles globales · colonnes absentes = règle non appliquée")
        accepted = dialog.exec()
        dialog.deleteLater()
        if not accepted:
            return
        book.rules = dialog.rules
        try:
            self.rule_store.save(book)
        except Exception as exc:
            self.error(exc)
            return
        self.rule_book = book
        if self.case:
            self.apply()
        self.statusBar().showMessage("Règles globales enregistrées pour toutes les analyses compatibles")

    def import_global_rules(self, path=None):
        if self.busy:
            return
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Importer et remplacer les règles globales", "", "Règles Fireblade (*.json)")
        if not path:
            return
        try:
            book = read_book(path)
            self.rule_store.replace(book)
        except Exception as exc:
            self.error(exc)
            return
        self.rule_book, self.global_rules_error = book, None
        if self.case:
            self.apply()
        self.statusBar().showMessage("Règles globales importées")

    def export_global_rules(self, path=None):
        if self.busy:
            return
        if self.global_rules_error:
            self.error(self.global_rules_error)
            return
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Exporter les règles globales", "regles-fireblade.json", "Règles Fireblade (*.json)")
        if not path:
            return
        try:
            target = Path(path).resolve()
            protected = {Path(s.path).resolve() for s in self.documents} | {Path(s.source_info["path"]).resolve() for s in self.documents}
            protected.add(self.rule_store.path.resolve())
            if target in protected:
                raise ValueError("Choisissez un fichier distinct de la configuration, des sources et des analyses")
            atomic_write(target, self.rule_book.to_bytes())
        except Exception as exc:
            self.error(exc)
            return
        self.statusBar().showMessage("Règles globales exportées ; aucune donnée d’analyse incluse")
