"""Multiple directory gestures, sequential imports and cancellation."""
import threading
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QTreeView

from fireblade.core.collection import Collection
from fireblade.core.paths import same_file
from fireblade.ui.app import Window
from fireblade.ui.folder_picker import FolderPicker
from tests.ui.test_start_workflow import until, idle


def test_directory_picker_accepts_ctrl_and_shift_selection(qt_application,tmp_path):
    folders=[tmp_path/name for name in ('alpha','beta','gamma')]
    for folder in folders:folder.mkdir()
    dialog=FolderPicker();dialog.setDirectory(str(tmp_path));dialog.show()
    tree=dialog.findChild(QTreeView,'treeView')
    try:
        try:
            until(qt_application,lambda:same_file(tree.model().filePath(tree.rootIndex()),tmp_path)
                  and all(tree.model().index(str(folder)).isValid() for folder in folders))
        except AssertionError as exc:
            raise AssertionError(dict(root=tree.model().filePath(tree.rootIndex()),
                directory=dialog.directory().absolutePath(), expected=str(tmp_path),
                items=[tree.model().index(i,0,tree.rootIndex()).data() for i in range(tree.model().rowCount(tree.rootIndex()))])) from exc
        QTest.qWait(100)
        indexes=[tree.model().index(str(folder)) for folder in folders]
        def click(index,modifiers=Qt.NoModifier):
            QTest.mouseClick(tree.viewport(),Qt.LeftButton,modifiers,pos=tree.visualRect(index).center())
            qt_application.processEvents()
        click(indexes[0]);click(indexes[2],Qt.ControlModifier)
        assert {Path(p) for p in dialog.selectedFiles()}=={folders[0],folders[2]}
        click(indexes[0]);click(indexes[2],Qt.ShiftModifier)
        assert {Path(p) for p in dialog.selectedFiles()}==set(folders)
        dialog.accept()
        assert dialog.result()==QDialog.Accepted
        assert {Path(p) for p in dialog.selectedFiles()}==set(folders)
    finally:dialog.close()


def test_multiple_folders_are_serial_and_saved(qt_application,tmp_path,monkeypatch):
    import fireblade.ui.collection as ui
    folders=[tmp_path/name for name in ('first','second')]
    for i,folder in enumerate(folders):
        folder.mkdir();(folder/'data.csv').write_text(f'ID\n{i}\n')
    monkeypatch.setattr(ui,'choose_collection_directories',lambda *a:[str(p) for p in folders])
    monkeypatch.setattr(ui.CollectionOrganizationDialog,'exec',lambda *a:QDialog.Accepted)
    release=threading.Event();entered=threading.Event();seen=[]
    original=Collection.publish_results
    def pause(self,start,entry):
        seen.append(self.root);original(self,start,entry)
        if self.root==folders[0]:entered.set();release.wait(20)
    monkeypatch.setattr(Collection,'publish_results',pause)
    window=Window(investigation_root=tmp_path/'cases');errors=[];window.error=errors.append
    data=window.create_investigation('Multiple folders')
    try:
        window.parse_collection()
        until(qt_application,lambda:entered.is_set() and window.case is not None and idle(window))
        assert seen==[folders[0]] and len(window._folder_queue)==1
        assert not window.close_investigation()
        release.set()
        until(qt_application,lambda:not window.disk_job and not window._folder_queue and not window.disk_pool.activeThreadCount() and idle(window))
        assert seen==folders and len(window.documents)==2 and not errors
        assert len(window.investigation_collections)==2
        assert window.close_investigation() and window.open_investigation(data['id'])
        until(qt_application,lambda:idle(window))
        assert len(window.documents)==2
    finally:
        release.set()
        until(qt_application,lambda:not window.disk_job and not window._folder_queue and not window.disk_pool.activeThreadCount() and idle(window))
        window.close()


def test_cancel_clears_not_started_directories(qt_application,tmp_path,monkeypatch):
    import fireblade.ui.collection as ui
    folders=[tmp_path/name for name in ('one','two')]
    for folder in folders:folder.mkdir()
    monkeypatch.setattr(ui,'choose_collection_directories',lambda *a:[str(p) for p in folders])
    monkeypatch.setattr(ui.CollectionOrganizationDialog,'exec',lambda *a:QDialog.Accepted)
    window=Window(investigation_root=tmp_path/'cases');window.create_investigation('Cancel queue')
    queued=[]
    monkeypatch.setattr(window.disk_pool,'start',queued.append)
    try:
        window.parse_collection()
        assert len(window._folder_queue)==1
        window.cancel_disk()
        assert not window._folder_queue
        queued[0].run()
        until(qt_application,lambda:window.disk_job is None)
        assert len(window.investigation_collections)==1
    finally:window.close()
