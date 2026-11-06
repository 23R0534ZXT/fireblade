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



def test_a_template_translates_a_message_built_at_run_time(monkeypatch):
    from fireblade.core.i18n import EN, templates
    monkeypatch.setitem(EN, "Analyse absente : {}", "Missing analysis: {}")
    templates.cache_clear()
    try:
        set_language('en')
        assert translate("Analyse absente : foo.duckdb") == "Missing analysis: foo.duckdb"
        # An exact entry still wins over a template.
        monkeypatch.setitem(EN, "Analyse absente : bar.duckdb", "Exact hit")
        assert translate("Analyse absente : bar.duckdb") == "Exact hit"
    finally:
        set_language('fr')
        templates.cache_clear()


def test_the_most_specific_template_wins(monkeypatch):
    from fireblade.core.i18n import EN, templates
    monkeypatch.setitem(EN, "{} en erreur", "{} in error")
    monkeypatch.setitem(EN, "Analyse en erreur : {}", "Analysis in error: {}")
    templates.cache_clear()
    try:
        set_language('en')
        assert translate("Analyse en erreur : 3") == "Analysis in error: 3"
        assert translate("Collecte en erreur") == "Collecte in error"
    finally:
        set_language('fr')
        templates.cache_clear()


def test_a_dialog_is_translated_when_it_appears(qt_application, monkeypatch):
    from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QTableWidget
    from fireblade.ui.language import install
    from fireblade.core.i18n import EN, templates
    monkeypatch.setitem(EN, "Colonne", "Column")
    templates.cache_clear()

    install(qt_application)
    set_language('en')
    dialog = QDialog()
    label = QLabel("Colonnes…", dialog)
    button = QPushButton("Appliquer à cette vue", dialog)
    table = QTableWidget(0, 1, dialog)
    table.setHorizontalHeaderLabels(["Colonne"])
    try:
        dialog.show()
        qt_application.processEvents()
        assert label.text() == "Columns…"
        assert button.text() == "Apply to this view"
        assert table.horizontalHeaderItem(0).text() == "Column"
        # Back to French, the source label is restored from what was recorded.
        set_language('fr')
        from fireblade.ui.language import translate_tree
        translate_tree(dialog)
        assert label.text() == "Colonnes…"
        assert button.text() == "Appliquer à cette vue"
        assert table.horizontalHeaderItem(0).text() == "Colonne"
    finally:
        set_language('fr')
        templates.cache_clear()
        dialog.close()
        dialog.setParent(None)
        dialog.deleteLater()
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_a_dynamic_label_keeps_its_new_text_across_a_language_switch(qt_application):
    from PySide6.QtWidgets import QLabel
    from fireblade.ui.language import translate_tree

    label = QLabel("3 analyses")
    try:
        set_language('en')
        translate_tree(label)
        label.setText("5 analyses")          # the code replaces the counter
        translate_tree(label)
        assert label.text() == "5 analyses"
        set_language('fr')
        translate_tree(label)
        assert label.text() == "5 analyses"  # not the stale "3 analyses"
    finally:
        set_language('fr')
        label.setParent(None)
        label.deleteLater()
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_a_status_message_is_translated_where_it_is_set(qt_application):
    from PySide6.QtWidgets import QMainWindow
    from fireblade.ui.language import install

    install(qt_application)
    window = QMainWindow()
    try:
        set_language('en')
        window.statusBar().showMessage("Colonnes…")
        assert window.statusBar().currentMessage() == "Columns…"
        set_language('fr')
        window.statusBar().showMessage("Colonnes…")
        assert window.statusBar().currentMessage() == "Colonnes…"
    finally:
        set_language('fr')
        window.close()
        window.setParent(None)
        window.deleteLater()
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_a_text_written_after_the_window_appeared_is_translated(qt_application):
    """A counter, an error or a combo filled once a case loads, not before."""
    from PySide6.QtWidgets import QComboBox, QLabel
    from fireblade.ui.language import apply_to_items, install

    install(qt_application)
    label, combo = QLabel(), QComboBox()
    try:
        set_language('en')
        label.setText("Colonnes…")
        assert label.text() == "Columns…"
        combo.addItem("Appliquer à cette vue")
        combo.addItem("Rechercher :")
        assert [combo.itemText(index) for index in range(combo.count())] == \
            ["Apply to this view", "Search:"]
        # French again: the stored source comes back, not the English label.
        set_language('fr')
        from fireblade.ui.language import translate_tree
        translate_tree(label)
        apply_to_items(combo)
        assert label.text() == "Colonnes…"
        assert combo.itemText(0) == "Appliquer à cette vue"
    finally:
        set_language('fr')
        for widget in (label, combo):
            widget.setParent(None)
            widget.deleteLater()
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_tab_titles_do_not_accumulate_ampersands(qt_application):
    """A tab title is escaped once, not once per language pass."""
    from PySide6.QtWidgets import QTabBar
    from fireblade.ui.language import translate_tree

    bar = QTabBar()
    bar.addTab("Chronologie & corrélations")
    try:
        set_language('fr')
        translate_tree(bar)
        first = bar.tabText(0)
        translate_tree(bar)
        translate_tree(bar)
        assert bar.tabText(0) == first
        assert '&&&&' not in bar.tabText(0)
        set_language('en')
        translate_tree(bar)
        assert bar.tabText(0) == 'Timeline && correlations'
        translate_tree(bar)
        assert bar.tabText(0) == 'Timeline && correlations'
    finally:
        set_language('fr')
        bar.setParent(None)
        bar.deleteLater()
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_a_table_cell_and_a_tree_node_are_translated(qt_application):
    """Items are not widgets: their label is caught where the code writes it."""
    from PySide6.QtWidgets import QTableWidgetItem, QTreeWidgetItem
    from fireblade.ui.language import install

    install(qt_application)
    try:
        set_language('en')
        cell = QTableWidgetItem("Non précisé")
        node = QTreeWidgetItem(["Analyses hors collecte"])
        assert cell.text() == "Not specified"
        assert node.text(0) == "Analyses outside a collection"
        cell.setText("Sans date")
        assert cell.text() == "Undated"
        # French again: the source stored on the item comes back.
        set_language('fr')
        from fireblade.ui.language import _recall
        cell.setText(_recall(cell))
        node.setText(0, _recall(node, 0))
        assert cell.text() == "Sans date"
        assert node.text(0) == "Analyses hors collecte"
    finally:
        set_language('fr')
        from PySide6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_a_model_header_is_translated(qt_application):
    from fireblade.ui.ioc_hunt import Rows
    from fireblade.ui.language import install
    from PySide6.QtCore import Qt

    install(qt_application)
    model = Rows(["Étape", "Gravité", "Fichier / périmètre"])
    try:
        set_language('en')
        labels = [model.headerData(column, Qt.Horizontal, Qt.DisplayRole) for column in range(3)]
        assert labels == ["Stage", "Severity", "File / scope"]
        set_language('fr')
        assert model.headerData(0, Qt.Horizontal, Qt.DisplayRole) == "Étape"
    finally:
        set_language('fr')


def test_a_message_built_by_concatenation_is_translated():
    """`"Lecture du filtre : " + value` is a template, value included."""
    try:
        set_language('en')
        assert translate("Lecture du filtre : toutes les lignes") == "Filter reading: all the rows"
    finally:
        set_language('fr')
