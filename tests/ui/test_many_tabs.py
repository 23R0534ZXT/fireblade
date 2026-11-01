from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from fireblade.ui.workspace_tabs import WorkspaceTabs


def settle(app,tabs):
    for _ in range(30):
        app.processEvents()
        if not tabs.pending:
            app.processEvents()
            if not tabs.pending:return
    raise AssertionError('Wrapping tabs did not settle')


def test_320_tabs_remain_accessible_without_covering_the_analysis(qt_application):
    tabs=WorkspaceTabs();tabs.resize(400,100);selected=[];closed=[]
    tabs.currentChanged.connect(selected.append);tabs.tabCloseRequested.connect(closed.append)
    tabs.replace_documents([f'case-{i:03}.csv' for i in range(320)],['']*320,319)
    tabs.set_multiline(True);tabs.show()
    try:
        settle(qt_application,tabs)
        assert tabs.count()==320 and sum(bar.count() for bar in tabs.rows)==320
        row_height=max(bar.sizeHint().height() for bar in tabs.rows)
        assert tabs.height()<=row_height*3
        assert tabs.area.verticalScrollBar().maximum()>0
        assert tabs.rect().contains(tabs.tabRect(319).center())
        tabs.setCurrentIndex(0);settle(qt_application,tabs)
        assert tabs.rect().contains(tabs.tabRect(0).center())
        tabs.area.verticalScrollBar().setValue(tabs.area.verticalScrollBar().maximum());qt_application.processEvents()
        bar,local=tabs.tab_widget(319)
        QTest.mouseClick(bar,Qt.LeftButton,pos=bar.tabRect(local).center())
        assert tabs.currentIndex()==319 and selected[-1]==319
        bar.tabCloseRequested.emit(local)
        assert closed==[319]
        tabs.set_multiline(False);settle(qt_application,tabs)
        assert len(tabs.rows)==1 and tabs.rows[0].count()==320
        assert tabs.currentIndex()==319
        tabs.set_multiline(True);tabs.setFixedWidth(260);settle(qt_application,tabs)
        assert tabs.height()<=max(bar.sizeHint().height() for bar in tabs.rows)*3
        assert tabs.rect().contains(tabs.tabRect(319).center())
    finally:tabs.close()


def test_click_target_survives_nested_event_loop_and_pending_rebuild(qt_application):
    from PySide6.QtCore import QEventLoop,QTimer
    from shiboken6 import isValid
    tabs=WorkspaceTabs();tabs.resize(400,100);tabs.replace_documents(['one','two','three'],['']*3,0);tabs.set_multiline(True);tabs.show()
    try:
        settle(qt_application,tabs);bar,local=tabs.tab_widget(1)
        observed=[]
        def switched(index):
            tabs.replace_documents(['one changed','two','three'],['']*3,index)
            loop=QEventLoop();QTimer.singleShot(20,loop.quit);loop.exec()
            observed.append(isValid(bar))
        tabs.currentChanged.connect(switched)
        tabs.schedule()
        QTest.mouseClick(bar,Qt.LeftButton,pos=bar.tabRect(local).center())
        assert observed==[True] and tabs.currentIndex()==1
        settle(qt_application,tabs)
        assert tabs.labels[0]=='one changed' and not tabs._interaction_depth and tabs._pressed_bar is None
    finally:tabs.close()
