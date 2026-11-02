from tests.ui.test_investigation_tools import loaded,settle
from fireblade.core.ioc_results import discover_hunts


def test_hunt_tab_counts_history_export_and_reset(qt_application,tmp_path):
    window,errors=loaded(qt_application,tmp_path)
    try:
        panel=window.ioc_panel
        window.workbench.setCurrentWidget(panel)
        panel.input.setPlainText('10.0.0.1\nabsent.example\ninvalid IOC')
        panel.launch();settle(qt_application,window)
        assert panel.store and panel.store.metadata['status']=='complete',errors
        assert panel.summary.rowCount()==2 and panel.model.rowCount()==4
        assert panel.store.metadata['rejected']==1
        panel.page(250);settle(qt_application,window);assert panel.offset==0 and panel.model.rowCount()==4
        root=panel.root();assert len(discover_hunts(root)[0])==1
        panel.select_ioc(panel.summary.index(1,0));settle(qt_application,window)
        assert panel.model.rowCount()==0
        panel.all_iocs();settle(qt_application,window);assert panel.model.rowCount()==4
        panel.refresh_history();settle(qt_application,window);assert panel.history.count()==2
        panel.reset_workspace();assert panel.store is None and panel.model.rowCount()==0
        assert not errors
    finally:window.close();settle(qt_application,window)


def test_source_row_return_restores_view(qt_application,tmp_path):
    from fireblade.core.models import View
    window,errors=loaded(qt_application,tmp_path)
    try:
        window.set_view(View(search='alice'));settle(qt_application,window)
        panel=window.ioc_panel;panel.input.setPlainText('10.0.0.1');panel.launch();settle(qt_application,window)
        panel.open_source(panel.model.index(0,0));settle(qt_application,window)
        assert window.view.filters and panel.origin is not None
        panel.return_to_hunt();settle(qt_application,window)
        assert not window.view.filters and window.workbench.currentWidget() is panel and not errors
    finally:window.close();settle(qt_application,window)
