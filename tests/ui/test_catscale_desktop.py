from fireblade.validation.catscale import verify_catscale


def test_catscale_families_render_and_restore_in_investigation(qt_application,tmp_path):
    result=verify_catscale(qt_application,tmp_path)
    assert result['status']=='passed'
    assert result['analyses']==7 and len(result['families'])==7
    assert result['case_restored'] and result['source_files_unchanged']


def test_folder_picker_imports_catscale_in_case_and_hayabusa_explains_evtx_requirement(qt_application,tmp_path,monkeypatch):
    import time
    from PySide6.QtWidgets import QDialog
    from fireblade.validation.catscale import write_corpus
    from fireblade.ui.app import Window
    import fireblade.ui.collection as ui
    source=write_corpus(tmp_path/'evidence')
    monkeypatch.setattr(ui.QFileDialog,'getExistingDirectory',lambda *args:str(source))
    def accept_artifacts(dialog):
        dialog.artifacts.setChecked(True)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(ui.CollectionOrganizationDialog,'exec',accept_artifacts)
    window=Window(require_case=False);errors=[];window.error=errors.append
    try:
        case=window.create_investigation('Linux collect',environment='linux')
        window.parse_collection()
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            qt_application.processEvents()
            if window.case and window.disk_job is None and not window.disk_pool.activeThreadCount() and not window.busy and not window.jobs and not window.pool.activeThreadCount() and not window.model.jobs and not getattr(window,'_collection_open_pending',False):break
            time.sleep(.005)
        assert len(window.documents)==7 and not errors
        assert window.investigation_library.folder(case['id']) in window.collection.output.parents
        window.analyze_collection()
        assert not window.jobs and 'EVTX Windows' in window.statusBar().currentMessage()
        assert 'CatScale Linux' in window.collection_report.toPlainText()
    finally:window.close()
