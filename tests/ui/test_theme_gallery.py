import copy
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialogButtonBox, QPushButton

from fireblade.core.preferences import Preferences,save_preferences,load_preferences
from fireblade.core.themes import THEMES,effective_palette
from fireblade.ui.preferences_dialog import PreferencesDialog
from fireblade.ui.theme import apply_theme
from fireblade.validation.appearance import rendered_contrast


@pytest.mark.parametrize('key',THEMES)
def test_each_gallery_theme_persists_and_renders_readable_controls(qt_application,tmp_path,key):
    preset=THEMES[key]
    p=Preferences(theme=preset.mode,theme_preset=key)
    save_preferences(p,tmp_path/'prefs.json');assert load_preferences(tmp_path/'prefs.json')==p
    try:
        apply_theme(qt_application,p.theme,effective_palette(p))
        palette=qt_application.palette()
        assert palette.color(QPalette.Base).name()==preset.palette()['base'].lower()
        assert palette.color(QPalette.Highlight).name()==preset.palette()['highlight'].lower()
        button=QPushButton('Ouvrir un fichier');button.setFocusPolicy(Qt.NoFocus)
        button.resize(180,36);button.show();QTest.qWait(20)
        assert rendered_contrast(button)['contrast']>=4.5
        button.setEnabled(False);QTest.qWait(20)
        assert rendered_contrast(button)['contrast']>=4.5
        button.close();button.deleteLater()
    finally:apply_theme(qt_application)


def test_gallery_preview_is_isolated_cancel_preserves_preferences_and_application(qt_application):
    original=Preferences(theme_palette={'base':'#efffff'})
    before=copy.deepcopy(original)
    app_palette=QPalette(qt_application.palette());stylesheet=qt_application.styleSheet()
    dialog=PreferencesDialog(original);dialog.show();qt_application.processEvents()
    try:
        for key,preset in THEMES.items():
            dialog.skin.setCurrentIndex(dialog.skin.findData(key));qt_application.processEvents()
            assert dialog.preview_table.palette().color(QPalette.Base).name()==preset.palette()['base'].lower()
            assert dialog.theme.currentData()==preset.mode
            assert qt_application.palette()==app_palette and qt_application.styleSheet()==stylesheet
        dialog.reject()
        assert original==before
    finally:dialog.close();dialog.deleteLater()


def test_gallery_accept_override_and_mode_change_keep_consistent_saved_choice(qt_application):
    dialog=PreferencesDialog(Preferences());dialog.show()
    try:
        dialog.skin.setCurrentIndex(dialog.skin.findData('forest'))
        dialog.palette={'highlight':'#987654'};dialog.refresh_preview()
        dialog.accept()
        p=dialog.preferences
        assert p.theme_preset=='forest' and p.theme=='dark'
        assert effective_palette(p)['highlight']=='#987654'
        assert effective_palette(p)['base']==THEMES['forest'].palette()['base']
    finally:dialog.close();dialog.deleteLater()
    dialog=PreferencesDialog(p)
    try:
        dialog.theme.setCurrentIndex(dialog.theme.findData('light'))
        assert dialog.skin.currentData()==''
        dialog.accept();assert dialog.preferences.theme_preset==''
    finally:dialog.close();dialog.deleteLater()


def test_preferences_small_window_scroll_keeps_confirmation_accessible(qt_application):
    dialog=PreferencesDialog(Preferences());dialog.resize(560,420);dialog.show();qt_application.processEvents()
    try:
        assert dialog.scroll.verticalScrollBar().maximum()>0
        dialog.scroll.ensureWidgetVisible(dialog.pins);qt_application.processEvents()
        buttons=dialog.findChild(QDialogButtonBox)
        for role in (QDialogButtonBox.Ok,QDialogButtonBox.Cancel):
            button=buttons.button(role)
            assert button.isVisible() and dialog.rect().contains(button.mapTo(dialog,button.rect().center()))
        assert dialog.scroll.viewport().rect().contains(dialog.pins.mapTo(dialog.scroll.viewport(),dialog.pins.rect().center()))
    finally:dialog.close();dialog.deleteLater()
