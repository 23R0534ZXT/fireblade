import time
from pathlib import Path
import pytest
from PySide6.QtCore import Qt

from fireblade.core.engine import Case
from fireblade.core.models import View, Filter, FilterGroup, FormatRule
from fireblade.core.auto_layout import local_path
from fireblade.runtime.windows_paths import user_directory
from fireblade.ui.app import Window
from fireblade.ui.dialogs import ImportDialog


def settle(app, window):
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        app.processEvents()
        if not window.jobs and not window.pool.activeThreadCount() and (not window.model or not window.model.jobs):return
        time.sleep(.005)
    pytest.fail('Background jobs did not settle')


def make_case(tmp_path,name,headers='User,Artifact,ID'):
    source=tmp_path/(name+'.csv');source.write_text(headers+('\n1,Test,Application,alice\n2,Test,Application,bob\n' if headers.count(',')==3 else '\nalice,MFT,001\nbob,EVTX,002\n'))
    case=Case(tmp_path/(name+'.timeline'));case.import_csv(source)
    return case


def test_changes_reload_for_new_file_and_preserve_session_snapshot(qt_application,tmp_path):
    w=Window(require_case=False);errors=[];w.error=errors.append
    try:
        first=make_case(tmp_path,'first');headers=list(first.headers)
        w.attach(first);settle(qt_application,w)
        view=View(groups=[1],filters=[Filter(0,'eq','alice')],right_pinned_columns=[2],
                  format_rules=[FormatRule(FilterGroup('and',[Filter(1,'eq','MFT')]),background='#ff0000')])
        w.set_view(view);settle(qt_application,w)
        w.tree.right_frozen.setColumnWidth(3,277)
        w.tree.setColumnHidden(1,True)
        header=w.tree.header();header.moveSection(header.visualIndex(2),1)
        w.detach()
        saved=local_path(headers,{})
        assert saved.is_file()
        w.attach(make_case(tmp_path,'second'));settle(qt_application,w)
        assert w.view.groups==[1] and w.view.filters==view.filters
        assert w.view.format_rules==view.format_rules and w.view.right_pinned_columns==[2]
        assert w.tree.right_frozen.columnWidth(3)==277 and w.tree.isColumnHidden(1)
        assert w.tree.header().visualIndex(2)==1
        assert w.case.count(w.view)==1
        # An explicitly restored session/tab remains authoritative.
        w.detach();w.attach(make_case(tmp_path,'session'),View(search='bob'),b'')
        # Empty header marks a fresh TLE session: automatic layout applies.
        settle(qt_application,w);assert w.view.groups==[1]
        state=bytes(w.tree.header().saveState())
        w.detach();w.attach(make_case(tmp_path,'saved-session'),View(search='bob'),state)
        settle(qt_application,w);assert w.view.search=='bob' and not w.view.groups
        assert not errors
    finally:settle(qt_application,w);w.close()


def test_new_csv_import_automatically_loads_saved_layout(qt_application,tmp_path,monkeypatch):
    w=Window(require_case=False);errors=[];w.error=errors.append
    try:
        w.attach(make_case(tmp_path,'first'));settle(qt_application,w)
        w.set_view(View(groups=[1],right_pinned_columns=[2]));settle(qt_application,w)
        w.tree.right_frozen.setColumnWidth(3,291)
        source=tmp_path/'next.csv';source.write_text('User,Artifact,ID\nalice,MFT,003\n')
        before=source.read_bytes()
        def accept(dialog):
            dialog.target.setText(str(tmp_path/'next.timeline'));dialog.accept();return dialog.result()
        monkeypatch.setattr(ImportDialog,'exec',accept)
        w.import_file(source);settle(qt_application,w)
        assert w.view.groups==[1] and w.view.right_pinned_columns==[2]
        assert w.tree.right_frozen.columnWidth(3)==291 and source.read_bytes()==before
        assert not errors
    finally:settle(qt_application,w);w.close()


def test_named_tle_local_xml_applies_to_fresh_session_and_invalid_file_is_not_overwritten(qt_application,tmp_path):
    w=Window(require_case=False);errors=[];w.error=errors.append
    path=user_directory()/'Layouts'/'Default'/'EvtxECmd.layout.local'
    path.parent.mkdir(parents=True)
    path.write_text('''<XtraSerializer><property name="Columns"><property name="Item1"><property name="FieldName">User</property><property name="VisibleIndex">0</property><property name="Width">287</property><property name="Fixed">Right</property></property></property></XtraSerializer>''')
    try:
        w.attach(make_case(tmp_path,'events','EventId,Provider,Channel,User'),View(),b'')
        settle(qt_application,w)
        assert w.view.right_pinned_columns==[3] and w.tree.right_frozen.columnWidth(4)==287
        w.detach()
        local=local_path(['EventId','Provider','Channel','User'],{})
        local.write_text('{broken')
        w.attach(make_case(tmp_path,'corrupt','EventId,Provider,Channel,User'));settle(qt_application,w)
        assert not w.view.right_pinned_columns and not w._layout_save_enabled
        assert any('Disposition automatique ignorée' in line for line in w.message_lines)
        w.detach()
        assert local.read_text()=='{broken' and not errors
    finally:settle(qt_application,w);w.close()


def test_manually_imported_xml_is_remembered_across_application_restart(qt_application,tmp_path,monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    xml=tmp_path/'arbitrary.layout.local'
    xml.write_text('''<XtraSerializer><property name="Columns"><property name="Item1"><property name="FieldName">ID</property><property name="VisibleIndex">0</property><property name="Width">319</property><property name="Fixed">Right</property></property></property></XtraSerializer>''')
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(xml),''))
    w=Window(require_case=False);errors=[];w.error=errors.append
    try:
        w.attach(make_case(tmp_path,'before-restart'));settle(qt_application,w)
        w.import_layout();settle(qt_application,w)
        assert w.view.right_pinned_columns==[2] and not errors
    finally:settle(qt_application,w);w.close()
    other=Window(require_case=False);other.error=errors.append
    try:
        other.attach(make_case(tmp_path,'after-restart'));settle(qt_application,other)
        assert other.view.right_pinned_columns==[2]
        assert other.tree.right_frozen.columnWidth(3)==319 and not errors
    finally:settle(qt_application,other);other.close()
