from PySide6.QtWidgets import QFileDialog,QMessageBox
from fireblade.ui.app import Window
from fireblade.core.engine import Case
from tests.ui.test_start_workflow import until,idle


def test_archive_reclaims_and_restores_from_catalogue(qt_application,tmp_path,monkeypatch):
    window=Window(investigation_root=tmp_path/'cases');errors=[];window.error=errors.append
    data=window.create_investigation('Cold storage');folder=window.investigation_library.folder(data['id'])
    source=tmp_path/'source.csv';source.write_text('ID\n1\n')
    case=Case(folder/'analysis.timeline');case.import_csv(source);case.bookmark(1,'Retain');case.close()
    window.load_case(folder/'analysis.timeline');until(qt_application,lambda:idle(window))
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a:(str(tmp_path/'backup.fireblade-case'),''))
    monkeypatch.setattr(QMessageBox,'question',lambda *a:QMessageBox.Yes)
    try:
        window.archive_and_release_selected()
        until(qt_application,lambda:idle(window))
        assert not errors and not (folder/'analysis.timeline').exists()
        assert window.investigation_library.read(data['id'])['storage_archive']
        window.open_investigation(data['id'])
        until(qt_application,lambda:window.case is not None and idle(window))
        assert window.case.bookmarks()=={1:'Retain'} and not errors
    finally:window.close()
