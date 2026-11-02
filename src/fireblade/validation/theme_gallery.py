"""Shared rendered-pixel checks for gallery themes, including frozen Windows QA."""
import copy
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QPushButton,QDialogButtonBox

from fireblade.core.themes import THEMES
from fireblade.ui.preferences_dialog import PreferencesDialog


def check_theme_gallery(window,captures=None):
    from fireblade.validation.appearance import rendered_contrast
    original=copy.deepcopy(window.preferences)
    button=QPushButton('Ouvrir un fichier',window)
    button.setWindowFlags(Qt.Tool);button.setFocusPolicy(Qt.NoFocus);button.resize(180,36)
    results={}
    try:
        for key,preset in THEMES.items():
            window.preferences.theme=preset.mode
            window.preferences.theme_preset=key
            window.preferences.theme_palette={}
            window.apply_preferences();button.setEnabled(True);button.show();QTest.qWait(30)
            enabled=rendered_contrast(button)
            button.setEnabled(False);QTest.qWait(20)
            disabled=rendered_contrast(button)
            assert QApplication.palette().color(QPalette.Base).name()==preset.palette()['base'].lower()
            if captures:
                target=Path(captures)/('gallery-'+key+'.png')
                assert window.grab().save(str(target))
            results[key]=dict(enabled=enabled,disabled=disabled)
        palette=QPalette(QApplication.palette());stylesheet=QApplication.instance().styleSheet()
        dialog=PreferencesDialog(window.preferences,window);dialog.resize(560,420);dialog.show();QTest.qWait(20)
        try:
            dialog.skin.setCurrentIndex(dialog.skin.findData('classic-blue'));QTest.qWait(20)
            assert QApplication.palette()==palette and QApplication.instance().styleSheet()==stylesheet
            assert dialog.pages.count()==4
            for page in range(4):
                dialog.pages.setCurrentIndex(page);QTest.qWait(10)
                assert dialog.page_scrolls[page].isVisible()
            buttons=dialog.findChild(QDialogButtonBox)
            for role in (QDialogButtonBox.Ok,QDialogButtonBox.Cancel):
                widget=buttons.button(role)
                assert dialog.rect().contains(widget.mapTo(dialog,widget.rect().center()))
            dialog.reject()
        finally:dialog.close();dialog.deleteLater()
        return results
    finally:
        button.close();button.deleteLater()
        window.preferences=original;window.apply_preferences()
