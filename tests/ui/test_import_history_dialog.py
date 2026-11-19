"""The import history: what came in, what did not, and why — with a way to try again."""
from PySide6.QtCore import Qt

from fireblade.ui.import_history import ImportHistoryDialog, summarise


def report():
    return dict(files=[
        dict(path='C:/ev/Security.evtx', status='complete',
             runs=[dict(tool='EvtxECmd', status='complete', outputs=[dict(csv='Security.csv')])]),
        dict(path='C:/ev/System.evtx', status='error', reason='EvtxECmd exited with code 1',
             runs=[dict(tool='EvtxECmd', status='error', error='Invalid file signature')]),
        dict(path='C:/ev/App.evtx', status='unsupported', reason='No reader recognised this file'),
        dict(path='C:/ev/Security - copie.evtx', status='duplicate',
             reason='Same content as Security.evtx ; read once', duplicate_of='C:/ev/Security.evtx'),
        dict(path='C:/ev/App (2).evtx', status='complete', similar_to='C:/ev/App.evtx',
             runs=[dict(tool='EvtxECmd', status='complete', outputs=[dict(csv='App.csv')])]),
    ])


def test_the_counts_tell_the_import_apart(qt_application):
    counts = summarise(report()['files'])
    assert counts == {'imported': 2, 'duplicate': 1, 'not_imported': 2, 'other': 0}


def test_the_dialog_filters_to_what_was_not_imported(qt_application):
    dialog = ImportHistoryDialog(report())
    try:
        assert dialog.table.rowCount() == 5
        dialog.filter.setCurrentIndex(dialog.filter.findData('not_imported'))
        assert dialog.table.rowCount() == 2
        names = {dialog.table.item(row, 0).text() for row in range(dialog.table.rowCount())}
        assert names == {'System.evtx', 'App.evtx'}, names
        dialog.filter.setCurrentIndex(dialog.filter.findData('duplicate'))
        assert dialog.table.rowCount() == 1
    finally:
        dialog.close()


def test_ticking_a_file_arms_the_retry_with_its_path(qt_application):
    seen = {}
    dialog = ImportHistoryDialog(report(), on_retry=lambda paths, reader: seen.update(paths=paths, reader=reader))
    try:
        assert not dialog.retry_button.isEnabled()
        dialog.filter.setCurrentIndex(dialog.filter.findData('not_imported'))
        dialog.table.item(0, 0).setCheckState(Qt.Checked)
        assert dialog.retry_button.isEnabled()
        assert dialog.checked_paths() == ['C:/ev/System.evtx']
    finally:
        dialog.close()


def test_the_details_say_why_and_what_it_resembles(qt_application):
    dialog = ImportHistoryDialog(report())
    try:
        dialog.table.selectRow(1)
        text = dialog.details.toPlainText()
        assert 'Invalid file signature' in text and 'System.evtx' in text
        dialog.table.selectRow(4)
        assert 'Resembles' in dialog.details.toPlainText() or 'Ressemblant' in dialog.details.toPlainText()
    finally:
        dialog.close()
