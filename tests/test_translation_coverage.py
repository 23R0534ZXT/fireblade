"""Every French string Fireblade can display has an English entry.

The interface is written in French; `core/i18n.py` displays the English. A
label missing from the table silently stays French, which is exactly what "tout
Fireblade traduit" forbids and what nobody notices file by file.

`tests/data/untranslated_french.txt` is the work list: what is still to
translate, one JSON string per line. Two rules keep it honest:

- a French string on a surface that is not in the file fails the first test, so
  new untranslated text cannot slip in;
- a line that is now translated fails the second test, so the file can only
  shrink. Regenerate it with
  `python -m scripts.i18n_inventory --write-baseline tests/data/untranslated_french.txt`.
"""
import json
import os

import pytest

from scripts.i18n_inventory import looks_french, missing

BASELINE = os.path.join(os.path.dirname(__file__), "data", "untranslated_french.txt")


def baseline():
    if not os.path.exists(BASELINE):
        return set()
    with open(BASELINE, encoding="utf-8") as handle:
        return {json.loads(line) for line in handle if line.strip()}


def test_no_french_string_on_a_surface_is_left_without_a_translation():
    absent = missing()
    new = sorted(set(absent) - baseline())
    assert not new, ("Ces libellés s'affichent sans traduction anglaise :\n  "
                     + "\n  ".join(new[:40])
                     + (f"\n  … et {len(new) - 40} autres" if len(new) > 40 else ""))


def test_the_work_list_only_shrinks():
    absent = missing()
    done = sorted(baseline() - set(absent))
    assert not done, ("Ces libellés sont traduits : retirez-les de "
                      "tests/data/untranslated_french.txt :\n  " + "\n  ".join(done[:40]))


def test_the_english_table_never_points_at_an_empty_label():
    from fireblade.core.i18n import EN
    assert all(source.strip() and target.strip() for source, target in EN.items())


def test_a_window_in_english_shows_no_french_leftover(qt_application, monkeypatch):
    """The real check: build the window as a new user gets it and read it."""
    from PySide6.QtWidgets import (QCheckBox, QComboBox, QGroupBox, QLabel, QLineEdit,
                                   QListWidget, QMenu, QMenuBar, QPlainTextEdit,
                                   QPushButton, QRadioButton, QTableWidget, QTabBar,
                                   QToolBar, QToolButton)

    from fireblade.core.i18n import set_language
    from fireblade.ui.app import Window
    from fireblade.ui.language import install

    monkeypatch.setenv("FIREBLADE_LANGUAGE", "en")
    install(qt_application)
    set_language("en")
    window = Window(require_case=False)   # opens in English, as a new user gets it
    try:
        window.show()
        for _ in range(6):
            qt_application.processEvents()
        seen = {}
        widgets = [window, *window.findChildren(object)]
        for widget in widgets:
            if isinstance(widget, (QLabel, QPushButton, QCheckBox, QRadioButton, QGroupBox, QToolButton)):
                text = widget.title() if isinstance(widget, QGroupBox) else widget.text()
                if looks_french(text):
                    seen.setdefault(text, type(widget).__name__)
            elif isinstance(widget, (QLineEdit, QPlainTextEdit)):
                if looks_french(widget.placeholderText()):
                    seen.setdefault(widget.placeholderText(), type(widget).__name__ + " placeholder")
            elif isinstance(widget, QTabBar):
                for index in range(widget.count()):
                    if looks_french(widget.tabText(index)):
                        seen.setdefault(widget.tabText(index), "tab")
            elif isinstance(widget, QComboBox):
                for index in range(widget.count()):
                    if looks_french(widget.itemText(index)):
                        seen.setdefault(widget.itemText(index), "combo")
            elif isinstance(widget, QListWidget):
                for index in range(widget.count()):
                    if looks_french(widget.item(index).text()):
                        seen.setdefault(widget.item(index).text(), "list")
            elif isinstance(widget, QTableWidget):
                for column in range(widget.columnCount()):
                    item = widget.horizontalHeaderItem(column)
                    if item is not None and looks_french(item.text()):
                        seen.setdefault(item.text(), "table header")
            elif isinstance(widget, (QMenuBar, QMenu)):
                for action in widget.actions():
                    if looks_french(action.text()):
                        seen.setdefault(action.text(), "menu")
            elif isinstance(widget, QToolBar):
                for action in widget.actions():
                    if looks_french(action.text()):
                        seen.setdefault(action.text(), "toolbar")
        assert not seen, ("Le français reste visible dans la fenêtre anglaise :\n  "
                          + "\n  ".join(f"[{where}] {text}" for text, where in sorted(seen.items())))
    finally:
        set_language("fr")
        window.close()
