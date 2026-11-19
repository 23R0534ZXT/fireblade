"""The progress line in the Imports panel: shown while it runs, hidden when it is over."""
from fireblade.ui.collection_report import CollectionReport


def report(status, percent=25.0, done=1, total=4):
    return dict(status=status, files=[], progress=dict(
        total=total, done=done, current='C:/evidence/Security.evtx', rows=12345,
        percent=percent, elapsed=30.0, remaining=90.0, phase='parse', finished=status != 'running'))


def test_a_running_import_shows_the_percentage_and_the_file_being_read(qt_application):
    panel = CollectionReport()
    panel.set_report(report('running'), '')
    try:
        assert panel.progress_widget.isVisibleTo(panel)
        assert panel.progress_bar.value() == 250
        text = panel.progress_text.text()
        assert '1 / 4' in text and 'Security.evtx' in text and '25.0 %' in text
    finally:
        panel.deleteLater()


def test_a_finished_import_hides_the_progress_line(qt_application):
    panel = CollectionReport()
    panel.set_report(report('complete', percent=100.0), '')
    try:
        assert not panel.progress_widget.isVisibleTo(panel)
    finally:
        panel.deleteLater()


def test_rows_are_shown_only_when_a_parser_counted_them(qt_application):
    panel = CollectionReport()
    try:
        panel.set_report(report('running'), '')
        assert '12 345' in panel.progress_text.text(), panel.progress_text.text()
        unknown = report('running')
        unknown['progress']['rows'] = 0
        panel.set_report(unknown, '')
        assert '12 345' not in panel.progress_text.text(), panel.progress_text.text()
    finally:
        panel.deleteLater()


def test_the_bar_stays_within_its_bounds(qt_application):
    panel = CollectionReport()
    try:
        panel.set_report(report('running', percent=250.0), '')
        assert panel.progress_bar.value() == 1000
        panel.set_report(report('running', percent=-3.0), '')
        assert panel.progress_bar.value() == 0
    finally:
        panel.deleteLater()
