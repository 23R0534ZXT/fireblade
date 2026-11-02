"""Built-in tutorial, user guide and license viewer; no external files are required."""
import json
import re
import unicodedata

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout

from fireblade.runtime.resources import build_info, resource_path


def show_text(parent, title, content, markdown=False, base_url=None):
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(850, 620)
    layout = QVBoxLayout(dialog)
    browser = QTextBrowser()
    browser.setOpenExternalLinks(False)
    browser.setOpenLinks(False)
    if base_url is not None:
        browser.document().setBaseUrl(QUrl.fromLocalFile(str(base_url)))

    def open_link(url):
        if url.scheme().lower() in {"http", "https", "mailto"}:
            QDesktopServices.openUrl(url)
        elif not url.path() and url.fragment():
            def slug(value):
                value = "".join(char for char in unicodedata.normalize("NFKD", value.lower())
                                if not unicodedata.combining(char))
                return re.sub(r"[\s-]+", "-", re.sub(r"[^\w\s-]", "", value).strip())

            target = slug(url.fragment())
            block = browser.document().begin()
            while block.isValid():
                if block.blockFormat().headingLevel() and slug(block.text()) == target:
                    cursor = browser.textCursor()
                    cursor.setPosition(block.position())
                    browser.setTextCursor(cursor)
                    browser.ensureCursorVisible()
                    return
                block = block.next()
        else:
            target = browser.document().baseUrl().resolved(url)
            if target.isLocalFile():
                from pathlib import Path
                path=Path(target.toLocalFile()).resolve()
                if path.suffix=='.md' and path.is_relative_to(resource_path('docs').resolve()) and path.is_file():
                    show_text(dialog,path.stem,path.read_text(encoding='utf-8'),markdown=True,base_url=path)
                    return
            QDesktopServices.openUrl(target)

    browser.anchorClicked.connect(open_link)
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
    show_text(parent, "Guide d’utilisation · Fireblade", path.read_text(encoding="utf-8"), markdown=True, base_url=path)


def show_tutorial(parent):
    path = resource_path("docs/guides/TUTORIEL-COMPLET.md")
    show_text(parent, "Tutoriel complet · Fireblade", path.read_text(encoding="utf-8"), markdown=True, base_url=path)


def show_investigation_guide(parent):
    path=resource_path('docs/guides/CHRONOLOGIE-ET-SAUVEGARDES.md')
    show_text(parent,'Chronologie, sauvegardes et rapports · Fireblade',path.read_text(encoding='utf-8'),markdown=True,base_url=path)


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
