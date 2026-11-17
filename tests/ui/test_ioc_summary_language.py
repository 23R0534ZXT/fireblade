"""The IOC hunt summary reads in the interface language, counters included."""


def test_the_hunt_summary_is_written_in_english(qt_application):
    from PySide6.QtWidgets import QMainWindow

    from fireblade.core.i18n import set_language
    from fireblade.ui.ioc_hunt import HuntPanel

    class FakeWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.main_toolbar = self.addToolBar('main')

        def can_open_file(self, **_):
            return True

        def run(self, *args, **kwargs):
            return None

        def error(self, message):
            raise AssertionError(message)

        def interrupt_queries(self):
            pass

    class Store:
        metadata = {'status': 'complete', 'scanned_rows': 2499027, 'matching_fields': 1525533,
                    'stored_hits': 250000, 'truncated': True, 'respect_filters': False, 'rejected': 1}

        def indicators(self):
            return []

        def sources(self):
            return [{'error': ''}]

        def close(self):
            pass

    window = FakeWindow()
    panel = HuntPanel(window)
    try:
        set_language('en')
        panel.page = lambda delta: None
        panel.display(Store())
        text = panel.status.text()
        assert 'Terminée' not in text, text
        assert 'Détails limités' not in text, text
        assert 'IOC rejetés' not in text, text
        assert 'Périmètre' not in text, text
        assert 'Completed' in text and 'details kept' in text, text
        assert panel.limit.prefix().strip().startswith('Max details'), panel.limit.prefix()
    finally:
        set_language('fr')
        panel.close()
        window.close()
