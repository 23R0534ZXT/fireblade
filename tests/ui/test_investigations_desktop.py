import time

from PySide6.QtCore import Qt

from fireblade.core.engine import Case
from fireblade.core.models import Filter, View
from fireblade.ui.app import Window
from fireblade.ui.dialogs import ImportDialog


def settle(app,window):
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        app.processEvents()
        if not window.jobs and not window.busy and not getattr(window,'_collection_open_pending',False) and not window.pool.activeThreadCount() and (window.model is None or not window.model.jobs) and not window.tabs.pending:return
        time.sleep(.005)
    raise AssertionError('Case workspace did not settle')


def analysis(tmp_path,name):
    source=tmp_path/(name+'.csv');source.write_text('User,ID\nalice,0001\nbob,0002\n')
    case=Case(tmp_path/(name+'.timeline'))
    try:case.import_csv(source);return case.path
    finally:case.close()


def test_close_and_restart_lists_case_without_loading_databases(qt_application,tmp_path,monkeypatch):
    path=analysis(tmp_path,'first');window=Window();errors=[];window.error=errors.append
    data=window.create_investigation('Enquête A','Poste compromis','windows')
    window.load_case(path);settle(qt_application,window)
    window.case.bookmark(1,'À vérifier')
    window.view.filters=[Filter(0,'eq','alice')];window.view.groups=[0]
    window.view.pinned_columns=[1];window.set_view(window.view);settle(qt_application,window)
    assert window.close()
    def forbidden(*args,**kwargs):raise AssertionError('Startup opened an analysis')
    with monkeypatch.context() as patch:
        patch.setattr('fireblade.ui.file_commands.Case',forbidden)
        restarted=Window();restarted.error=errors.append
    try:
        assert restarted.case is None and restarted.model is None and restarted.documents==[]
        assert restarted.active_investigation is None
        assert restarted.workbench.currentIndex()==restarted.cases_tab_index
        assert restarted.cases_table.rowCount()==1
        assert restarted.cases_table.item(0,0).text()=='Enquête A'
        assert restarted.open_investigation(data['id']);settle(qt_application,restarted)
        assert restarted.view.filters==[Filter(0,'eq','alice')]
        assert restarted.view.groups==[0] and restarted.view.pinned_columns==[1]
        assert restarted.case.bookmarks()=={1:'À vérifier'}
        assert not errors
    finally:restarted.close()


def test_switching_cases_saves_session_and_releases_inactive_connection(qt_application,tmp_path):
    first=analysis(tmp_path,'one');second=analysis(tmp_path,'two')
    window=Window();errors=[];window.error=errors.append
    try:
        one=window.create_investigation('One');window.load_case(first);settle(qt_application,window)
        window.search.setText('alice');window.apply();settle(qt_application,window)
        connection=window.case.db
        two=window.create_investigation('Two');settle(qt_application,window)
        assert window.case is None and not window.documents
        import duckdb,pytest
        with pytest.raises(duckdb.ConnectionException):connection.execute('SELECT 1')
        window.load_case(second);settle(qt_application,window)
        assert window.open_investigation(one['id']);settle(qt_application,window)
        assert window.case.path==first and window.view.search=='alice'
        assert len(window.documents)==1
        assert window.open_investigation(two['id']);settle(qt_application,window)
        assert window.case.path==second and window.view.search==''
        assert not errors
    finally:window.close()


def test_missing_analysis_does_not_close_current_case(qt_application,tmp_path):
    path=analysis(tmp_path,'valid');window=Window();errors=[];window.error=errors.append
    try:
        broken=window.create_investigation('Broken');window.load_case(path);settle(qt_application,window)
        assert window.close_investigation();settle(qt_application,window)
        path.unlink()
        current=window.create_investigation('Current')
        assert not window.open_investigation(broken['id'])
        assert window.active_investigation['id']==current['id'] and errors
    finally:window.close()


def test_failed_save_prevents_case_switch_and_close(qt_application,tmp_path,monkeypatch):
    window=Window();errors=[];window.error=errors.append
    try:
        one=window.create_investigation('One');other=window.investigation_library.create('Other')
        def denied(*args,**kwargs):raise PermissionError('locked')
        with monkeypatch.context() as patch:
            patch.setattr(window.investigation_library,'save',denied)
            assert not window.open_investigation(other['id'])
            assert not window.close()
            assert window.active_investigation['id']==one['id'] and len(errors)==2
    finally:window.close()


def test_archive_search_and_default_import_folder(qt_application,tmp_path):
    window=Window();errors=[];window.error=errors.append
    try:
        one=window.create_investigation('Laptop Alice','Poste Windows','windows')
        dialog=ImportDialog(tmp_path/'evidence.csv',window)
        try:assert dialog.values()[0].parent==window.investigation_library.folder(one['id'])/'Analyses'
        finally:dialog.close()
        window.create_investigation('Serveur Linux',environment='linux')
        window.cases_search.setText('Alice');assert window.cases_table.rowCount()==1
        window.cases_table.selectRow(0);window.archive_selected_investigation()
        assert window.cases_table.rowCount()==0
        window.cases_archived.setChecked(True);assert window.cases_table.rowCount()==1
        window.cases_table.selectRow(0);window.archive_selected_investigation()
        assert window.investigation_library.read(one['id'])['status']=='open'
        assert not errors
    finally:window.close()


def test_multiple_tabs_active_view_and_annotations_survive_restart(qt_application,tmp_path):
    one=analysis(tmp_path,'tab-one');two=analysis(tmp_path,'tab-two')
    window=Window();errors=[];window.error=errors.append
    data=window.create_investigation('Deux analyses')
    for path in (one,two):window.load_case(path);settle(qt_application,window)
    window.case.bookmark(2,'Deuxième analyse')
    window.switch_document(0);settle(qt_application,window)
    window.set_view(View(sort_column=1,sort_type='number',descending=True,pinned_columns=[0]));settle(qt_application,window)
    window.case.bookmark(1,'Première analyse')
    assert window.close()
    reopened=Window();reopened.error=errors.append
    try:
        assert reopened.open_investigation(data['id']);settle(qt_application,reopened)
        assert len(reopened.documents)==2 and reopened.active_document==0
        assert reopened.case.path==one and reopened.view.sort_column==1 and reopened.view.descending
        assert reopened.case.bookmarks()=={1:'Première analyse'}
        reopened.switch_document(1);settle(qt_application,reopened)
        assert reopened.case.path==two and reopened.case.bookmarks()=={2:'Deuxième analyse'}
        assert not errors
    finally:reopened.close()


def test_case_keeps_two_collections_and_their_views(qt_application,tmp_path):
    from fireblade.core.collection import Collection,ToolPack
    window=Window();errors=[];window.error=errors.append
    try:
        data=window.create_investigation('Collectes multiples')
        first_path=None
        for index in range(2):
            root=tmp_path/f'evidence-{index}';root.mkdir();(root/'users.csv').write_text('User\nalice\nbob\n')
            output=window.investigation_data_directory('Collectes')/f'collecte-{index}'
            window.collection=Collection(root,output,ToolPack(tmp_path/'pack'),window.settings,organization='artifacts')
            window.start_collection_job(window.collection.parse);settle(qt_application,window)
            if index==0:
                first_path=window.case.path
                window.search.setText('alice');window.apply();settle(qt_application,window)
        assert len(window.documents)==2 and len(window.investigation_collections)==2
        assert window.case.path!=first_path and window.view.search==''
        window.switch_document(0);settle(qt_application,window)
        assert window.view.search=='alice'
        assert window.close_investigation();settle(qt_application,window)
        assert window.open_investigation(data['id']);settle(qt_application,window)
        assert len(window.documents)==2 and window.case_collections_combo.count()==2
        assert window.view.search=='alice' and not errors
    finally:window.close()


def test_queued_imports_block_switch_and_metadata_edits_keep_local_session(qt_application,tmp_path):
    window=Window();errors=[];window.error=errors.append
    try:
        one=window.create_investigation('Original');other=window.investigation_library.create('Other')
        window.open_queue=[tmp_path/'pending.csv']
        assert not window.open_investigation(other['id'])
        assert window.active_investigation['id']==one['id']
        window.open_queue.clear()
        window.investigation_library.update(one['id'],name='Renommé ailleurs')
        assert window.save_investigation()
        assert window.active_investigation['name']=='Renommé ailleurs' and not errors
    finally:window.close()


def test_frozen_case_qualification_flow_uses_real_widgets_and_databases(qt_application,tmp_path):
    from fireblade.validation.investigations import verify_investigations
    result=verify_investigations(qt_application,tmp_path/'qualification')
    assert result['cases']==2 and result['restored_analyses']==2
    assert result['unloaded_startup'] and result['session_and_notes_restored']


def test_pending_collection_result_blocks_closing_or_switching_case(qt_application,tmp_path):
    from fireblade.core.collection import Collection,ToolPack
    root=tmp_path/'input';root.mkdir();(root/'records.csv').write_text('User\nalice\n')
    window=Window();errors=[];window.error=errors.append
    try:
        data=window.create_investigation('Pending collection')
        window.collection=Collection(root,tmp_path/'output',ToolPack(tmp_path/'pack'),window.settings)
        report=window.collection.parse()
        window.collection_finished(report)
        assert not window.close()
        assert window.create_investigation('Wrong case') is None
        settle(qt_application,window)
        assert window.active_investigation['id']==data['id']
        assert window.case is not None and len(window.documents)==1 and not errors
    finally:window.close()


def test_same_case_cannot_be_opened_in_two_windows(qt_application,tmp_path):
    first=Window();second=Window();errors=[];second.error=errors.append
    try:
        data=first.create_investigation('Unique owner')
        assert not second.open_investigation(data['id'])
        assert errors and 'déjà ouvert' in str(errors[0])
        assert second.active_investigation is None
        assert first.close_investigation();settle(qt_application,first)
        assert second.open_investigation(data['id'])
    finally:first.close();second.close()


def test_large_old_case_catalogue_stays_unloaded_and_searchable(qt_application,tmp_path,monkeypatch):
    from fireblade.core.investigations import InvestigationLibrary
    library=InvestigationLibrary(tmp_path/'catalogue')
    for index in range(300):library.create(f'Ancienne enquête {index:04d}',environment='linux' if index%2 else 'windows')
    def forbidden(*args,**kwargs):raise AssertionError('Catalogue loaded an analysis database')
    with monkeypatch.context() as patch:
        patch.setattr('fireblade.ui.file_commands.Case',forbidden)
        window=Window(investigation_root=library.root)
    try:
        assert window.cases_table.rowCount()==300 and window.case is None and window.documents==[]
        window.cases_search.setText('0299');assert window.cases_table.rowCount()==1
        assert window.cases_table.item(0,0).text()=='Ancienne enquête 0299'
        window.cases_search.clear();assert window.cases_table.rowCount()==300
        assert window.active_investigation is None
    finally:window.close()
