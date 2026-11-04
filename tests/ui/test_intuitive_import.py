"""Background folder parsing stays interactive and preserves its case on restart."""
import threading

import pytest
from PySide6.QtWidgets import QDialog

from fireblade.core.collection import Collection
from fireblade.ui.app import Window
from tests.ui.test_start_workflow import until, idle


@pytest.mark.parametrize('organization', ['files', 'artifacts', 'combined'])
def test_folder_import_background_and_case_restore(qt_application, tmp_path, monkeypatch, organization):
    import fireblade.ui.collection as ui
    source=tmp_path/'evidence';source.mkdir()
    (source/'data.csv').write_text('ID,User\n001,alice\n002,bob\n')
    release=threading.Event();entered=threading.Event()
    original=Collection.publish_results
    def pause(self, start, entry):
        original(self,start,entry);entered.set();release.wait(20)
    monkeypatch.setattr(Collection,'publish_results',pause)
    monkeypatch.setattr(ui,'choose_collection_directories',lambda *a:[str(source)])
    def accept(dialog):
        {'files':dialog.progressive,'artifacts':dialog.artifacts,'combined':dialog.combined}[organization].setChecked(True)
        return QDialog.Accepted
    monkeypatch.setattr(ui.CollectionOrganizationDialog,'exec',accept)
    window=Window(investigation_root=tmp_path/'cases');errors=[];window.error=errors.append
    data=window.create_investigation('Folder background')
    try:
        window.parse_collection()
        until(qt_application,lambda:entered.is_set())
        assert window.disk_job is not None and not window.busy
        assert window.centralWidget().isEnabled()
        assert window.collection.settings.threads==1
        assert window.collection.settings.memory_mb==64
        assert not window.close_investigation()
        if organization=='files':
            until(qt_application,lambda:window.case is not None and idle(window))
            window.search.setText('alice');window.apply()
            until(qt_application,lambda:idle(window))
            assert window.case.count(window.view)==1
        release.set()
        until(qt_application,lambda:window.disk_job is None and not window.disk_pool.activeThreadCount() and idle(window))
        assert len(window.documents)==1 and not errors
        assert not window.disk_drain.isActive()
        assert window.close_investigation()
        assert window.open_investigation(data['id'])
        until(qt_application,lambda:idle(window))
        assert len(window.documents)==1
    finally:
        release.set()
        until(qt_application,lambda:window.disk_job is None and not window.disk_pool.activeThreadCount() and idle(window))
        window.close()


def test_commands_group_evidence_and_keep_case_gate(qt_application,tmp_path):
    window=Window(investigation_root=tmp_path/'cases')
    try:
        menus={a.text().replace('&',''):a.menu() for a in window.menuBar().actions()}
        assert list(menus)[:3]==['Case','Analyse','Détection']
        analysis={a.text():a for a in menus['Analyse'].actions()}
        assert 'Parser un dossier…' in analysis
        assert 'Importer un fichier…' in analysis
        assert not menus['Analyse'].menuAction().isEnabled()
        window.create_investigation('Menus')
        assert menus['Analyse'].menuAction().isEnabled() and analysis['Parser un dossier…'].isEnabled()
        assert window.workbench.tabText(1)=='Imports'
        assert window.workbench.indexOf(window.detection_panel)>=0
        assert window.workbench.indexOf(window.coverage_panel)==-1
        assert not window.coverage_dialog.isVisible()
        window.coverage_panel.open()
        assert window.coverage_dialog.isVisible()
    finally:window.close()
