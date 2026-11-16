import time

from fireblade.ui.app import Window
from fireblade.core.collection import Collection, ToolPack


def settle(app, window):
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        app.processEvents()
        if window.case and not window.jobs and not window.pool.activeThreadCount() and not window.model.jobs:
            return
        time.sleep(.01)
    raise AssertionError('Collection session did not open')


def test_native_collection_opens_results_and_keeps_report(qt_application,tmp_path):
    root=tmp_path/'evidence';root.mkdir()
    (root/'users.csv').write_text('User,Value\nalice,1\nbob,2\n')
    window=Window(require_case=False);errors=[];window.error=errors.append
    try:
        window.collection=Collection(root,tmp_path/'results',ToolPack(tmp_path/'missing'),window.settings)
        window.start_collection_job(window.collection.parse)
        settle(qt_application,window)
        assert len(window.documents)==1
        assert window.model.case.headers==['User','Value']
        assert 'Terminé' in window.collection_report.toPlainText()
        assert window.workbench.currentIndex()==0
        assert not errors
    finally:
        if window.jobs:
            window.interrupt_queries()
        window.close()


def test_collection_organization_dialog_exposes_two_choices(qt_application):
    from fireblade.ui.collection import CollectionOrganizationDialog
    from PySide6.QtWidgets import QDialogButtonBox
    dialog=CollectionOrganizationDialog()
    try:
        assert dialog.organization()=='files'
        dialog.combined.click()
        assert dialog.organization()=='combined'
        assert not dialog.artifacts.isChecked()
        dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok).click()
        assert dialog.result()==1
    finally:dialog.close()


def test_grouped_collection_opens_with_saved_group_by(qt_application,tmp_path,monkeypatch):
    root=tmp_path/'source';root.mkdir();(root/'users.csv').write_text('User\nalice\n')
    window=Window(require_case=False);errors=[];window.error=errors.append
    automatic=[]
    monkeypatch.setattr(window,'restore_format_layout',lambda:automatic.append(True))
    try:
        window.collection=Collection(root,tmp_path/'work',ToolPack(tmp_path/'pack'),window.settings,organization='combined')
        window.start_collection_job(window.collection.parse)
        settle(qt_application,window)
        assert len(window.documents)==1
        assert window.case.headers[0]=='Artefact'
        assert not automatic
        assert window.view.groups==[0]
        assert window.model.node(window.model.index(0,0)).values[0]=='Exports CSV'
        assert not errors
    finally:window.close()


def test_import_prompt_applies_organization_and_cancel_does_not_start(qt_application,tmp_path,monkeypatch):
    import fireblade.ui.collection as ui
    from PySide6.QtWidgets import QDialog
    source=tmp_path/'source';source.mkdir();(source/'data.csv').write_text('ID\n001\n')
    monkeypatch.setattr(ui,'choose_collection_directories',lambda *args:[str(source)])
    monkeypatch.setattr(ui,'user_directory',lambda:tmp_path/'profile')
    window=Window(require_case=False);errors=[];window.error=errors.append
    try:
        monkeypatch.setattr(ui.CollectionOrganizationDialog,'exec',lambda self:QDialog.DialogCode.Rejected)
        window.parse_collection()
        assert window.collection is None and not window.jobs
        def accept_combined(dialog):
            dialog.combined.setChecked(True)
            return QDialog.DialogCode.Accepted
        monkeypatch.setattr(ui.CollectionOrganizationDialog,'exec',accept_combined)
        window.parse_collection()
        settle(qt_application,window)
        assert window.collection.report['organization']=='combined'
        assert window.view.groups==[0]
        assert not errors
    finally:window.close()


def wait_for(app, predicate, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(.01)
    return False


def test_reading_a_file_again_opens_the_analysis_it_produced(qt_application, tmp_path):
    """The button path end to end: dialog choice, worker, import, new tab."""
    root = tmp_path / 'evidence'
    root.mkdir()
    (root / 'users.csv').write_text('User,Value\nalice,1\n', encoding='utf-8')
    (root / 'note.txt').write_bytes('Réunion du service\n2026-11-14 08:12 démarrage\n'.encode('utf-8'))
    window = Window(require_case=False)
    errors = []
    window.error = errors.append
    try:
        window.collection = Collection(root, tmp_path / 'results', ToolPack(tmp_path / 'missing'),
                                       window.settings)
        window.start_collection_job(window.collection.parse)
        settle(qt_application, window)
        assert len(window.documents) == 1
        entry = next(e for e in window.collection.report['files'] if e['path'].endswith('note.txt'))
        assert entry['status'] == 'unsupported'

        window.analyse_with_reader(entry['path'], 'text')

        assert wait_for(qt_application, lambda: len(window.documents) == 2
                        and not window.pool.activeThreadCount()), 'analyse non ouverte'
        assert window.workbench.currentIndex() == 0
        assert window.model.case.headers[:3] == ['Source', 'Ligne', 'Horodatage']
        assert entry['status'] == 'complete' and entry['tools'] == ['TextReader']
        assert 'TextReader' in window.collection_report.toPlainText()
        assert not errors
    finally:
        if window.jobs:
            window.interrupt_queries()
        window.close()
