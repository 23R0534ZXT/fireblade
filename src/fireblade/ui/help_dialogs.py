"""Built-in user guide and license viewer; no external files are required."""
import json

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout

from fireblade.runtime.resources import build_info, resource_path


def show_text(parent, title, content, markdown=False):
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(850, 620)
    layout = QVBoxLayout(dialog)
    browser = QTextBrowser()
    browser.setOpenExternalLinks(True)
    if markdown:
        browser.setMarkdown(content)
    else:
        browser.setPlainText(content)
    layout.addWidget(browser)
    buttons = QDialogButtonBox(QDialogButtonBox.Close)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()
    dialog.deleteLater()


def show_guide(parent):
    path = resource_path("docs/guides/UTILISATION.md")
    show_text(parent, "Guide d’utilisation · Fireblade", path.read_text(encoding="utf-8"), markdown=True)


def show_licenses(parent):
    parts = [resource_path("LICENSE").read_text(encoding="utf-8")]
    legal = resource_path("legal")
    if not legal.exists():
        legal = resource_path("licenses")
    if legal.exists():
        for path in sorted(legal.rglob("*")):
            if path.is_file():
                parts.append(f"\n{'=' * 60}\n{path.relative_to(legal)}\n{'=' * 60}\n" + path.read_text(encoding="utf-8", errors="replace"))
    else:
        parts.append("Dépendances : DuckDB (MIT), openpyxl (MIT), PySide6 / Shiboken6 / Qt (LGPL ou licence commerciale). Les textes distribués avec les bibliothèques sont inclus lors de la construction Windows.")
    show_text(parent, "Licences · Fireblade", "\n\n".join(parts))


def show_about(parent):
    info = build_info()
    show_text(parent, "À propos de Fireblade", "Fireblade\n\nExploration locale de données forensic\n\n" + json.dumps(info, ensure_ascii=False, indent=2))
