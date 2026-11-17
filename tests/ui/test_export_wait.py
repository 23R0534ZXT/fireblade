"""An export that cannot start yet has to say so."""


def test_the_coverage_export_says_why_it_waits(qt_application, tmp_path):
    from tests.ui.test_investigation_tools import loaded, settle
    window, errors = loaded(qt_application, tmp_path)
    try:
        panel = window.coverage_panel
        panel.report = {'findings': [], 'counts': {'error': 0, 'warning': 0}, 'sources': [], 'created': 'x'}
        window.can_open_file = lambda *args, **kwargs: False
        panel.export()
        assert 'query' in panel.status.text().lower(), panel.status.text()
        assert not errors
    finally:
        window.close()
        settle(qt_application, window)
