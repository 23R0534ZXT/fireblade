"""Interface language: English by default, French on demand, French source text."""
import pytest

from fireblade.core.i18n import EN, current_language, fallback_language, set_language, translate


def test_english_is_the_default_for_a_fresh_profile(monkeypatch):
    monkeypatch.delenv('FIREBLADE_LANGUAGE', raising=False)
    from fireblade.core.preferences import Preferences
    assert Preferences().language == 'en'
    assert fallback_language() == 'en'


def test_every_translation_has_a_distinct_english_label():
    assert len(set(EN.values())) > len(EN) * 0.8
    assert all(value.strip() for value in EN.values())


def test_french_returns_the_source_text_untouched():
    try:
        set_language('fr')
        assert translate('Colonnes…') == 'Colonnes…'
        assert translate('&Affichage') == '&Affichage'
    finally:
        set_language('en')


def test_english_translates_known_labels_and_leaves_the_rest_alone():
    try:
        set_language('en')
        assert translate('Colonnes…') == 'Columns…'
        assert translate('&Affichage') == '&View'
        assert translate('3 analyses ouvertes') == '3 analyses ouvertes'
        assert translate('') == ''
    finally:
        set_language('en')


def test_an_unknown_language_is_refused():
    before = current_language()
    with pytest.raises(ValueError):
        set_language('de')
    assert current_language() == before


def all_labels(window):
    """Every menu entry, submenus included."""
    labels = []

    def walk(menu):
        for action in menu.actions():
            labels.append(action.text())
            if action.menu() is not None:
                walk(action.menu())

    for action in window.menuBar().actions():
        if action.menu() is not None:
            walk(action.menu())
    return labels


def test_switching_in_the_preferences_translates_the_menu_bar(qt_application, monkeypatch):
    monkeypatch.setenv('FIREBLADE_LANGUAGE', 'fr')
    from fireblade.ui.app import Window
    window = Window(require_case=False)
    try:
        assert '&Affichage' in [action.text() for action in window.menuBar().actions()]
        window.preferences.language = 'en'
        window.apply_preferences()
        titles = [action.text() for action in window.menuBar().actions()]
        assert '&View' in titles and '&Affichage' not in titles
        assert 'Columns…' in all_labels(window)
        window.preferences.language = 'fr'
        window.apply_preferences()
        assert '&Affichage' in [action.text() for action in window.menuBar().actions()]
        assert 'Colonnes…' in all_labels(window)
    finally:
        window.close()
        set_language('fr')


def test_preferences_dialog_offers_and_saves_the_language(qt_application):
    from PySide6.QtCore import QCoreApplication, QEvent
    from fireblade.core.preferences import Preferences
    from fireblade.ui.preferences_dialog import PreferencesDialog

    dialog = PreferencesDialog(Preferences(language='en'))
    try:
        codes = [dialog.language.itemData(row) for row in range(dialog.language.count())]
        assert codes == ['en', 'fr']
        assert dialog.language.currentData() == 'en'
        dialog.language.setCurrentIndex(dialog.language.findData('fr'))
        dialog.accept()
        assert dialog.preferences.language == 'fr'
    finally:
        dialog.close()
        dialog.setParent(None)
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_preferences_reject_an_unknown_language():
    from fireblade.core.preferences import Preferences
    preferences = Preferences(language='klingon')
    with pytest.raises(ValueError):
        preferences.validate()
    Preferences(language='en').validate()
    Preferences(language='fr').validate()
