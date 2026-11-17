"""A reason written by the engine in French still reads in the interface language."""


def test_the_findings_table_speaks_the_interface_language(qt_application, tmp_path):
    from tests.ui.test_investigation_tools import loaded, settle
    from fireblade.core.i18n import set_language
    window, errors = loaded(qt_application, tmp_path)
    try:
        panel = window.coverage_panel
        panel.record('Import', 'error', 'permission denied', '/missing.csv')
        set_language('en')
        panel.mode.setCurrentIndex(1)
        panel.filter()
        assert panel.model.rowCount() >= 1
        cells = [panel.model.index(row, column).data()
                 for row in range(panel.model.rowCount())
                 for column in range(panel.model.columnCount())]
        assert 'Erreur' not in [str(cell) for cell in cells], cells
        assert not errors
    finally:
        set_language('fr')
        window.close()
        settle(qt_application, window)
