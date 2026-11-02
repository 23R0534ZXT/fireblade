from fireblade.core.models import AnalysisSnapshot, View
from fireblade.core.sessions import MAX_SESSION_BYTES, read_session, write_session
from fireblade.ui.app import Window


def test_rejected_session_save_reports_error_and_keeps_previous_file(qt_application, tmp_path):
    window = Window()
    errors = []
    window.error = errors.append
    source = tmp_path / 'source.csv'
    source.write_text('ID\n001\n', encoding='utf-8')
    database = tmp_path / 'analysis.timeline'
    database.touch()
    document = AnalysisSnapshot(str(database), {'path': str(source)}, View(), b'')
    target = tmp_path / 'workspace.fireblade-session'
    write_session(target, [document], 0)
    before = target.read_bytes()
    window.documents = [document]
    window.active_document = 0
    window.statusBar().showMessage('Avant la sauvegarde')
    document.view.search = 'a' * MAX_SESSION_BYTES
    try:
        window.save_session(target)
        assert len(errors) == 1 and '4 Mo' in str(errors[0])
        assert target.read_bytes() == before
        assert read_session(target)[0][0].view.search == ''
        assert window.statusBar().currentMessage() == 'Avant la sauvegarde'
        assert not list(tmp_path.glob('*.partial'))
    finally:
        window.documents = []
        window.close()
