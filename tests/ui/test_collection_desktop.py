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
    window=Window();errors=[];window.error=errors.append
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
