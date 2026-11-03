import csv
import time
from dataclasses import replace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView

from fireblade.core.engine import Case
from fireblade.core.models import View
from fireblade.core.tle_layout import read_tle_layout
from fireblade.ui.app import Window
from fireblade.ui.row_heights import RowHeightDialog


def settle(app,window):
    end=time.monotonic()+15
    while time.monotonic()<end:
        app.processEvents()
        if not window.jobs and not window.pool.activeThreadCount() and not window.model.jobs and not window.tree.row_heights.pending:return
        time.sleep(.005)
    raise AssertionError('Row layout did not settle')


def test_auto_height_exceeds_three_lines_and_stays_shared_after_resize(qt_application,tmp_path,monkeypatch):
    source=tmp_path/'s.csv'
    with source.open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['Text','Other','N'])
        writer.writerow(['\n'.join(f'line {i}' for i in range(8)),'long words '*30,'1'])
        writer.writerow(['short','short','2'])
    case=Case(tmp_path/'s.timeline');case.import_csv(source)
    view=View(auto_row_height=True,layout_styles={'row':{'word_wrap':True}},pinned_columns=[0],right_pinned_columns=[2])
    window=Window(require_case=False);errors=[];window.error=errors.append
    try:
        window.attach(case,view);window.show();settle(qt_application,window)
        tree=window.tree;tree.frozen.setColumnWidth(1,140);tree.setColumnWidth(2,120);settle(qt_application,window)
        height=tree.visualRect(window.model.index(0,2)).height()
        assert height>3*window.fontMetrics().height()
        assert window.model.index(0,1).data().count('\n')==7
        for panel,column in [(tree.frozen,1),(tree.right_frozen,3)]:
            assert panel.visualRect(window.model.index(0,column)).height()==height
            assert panel.visualRect(window.model.index(1,column)).top()==tree.visualRect(window.model.index(1,2)).top()
            assert panel.verticalScrollMode()==QAbstractItemView.ScrollPerPixel
        assert tree.visualRect(window.model.index(1,2)).height()<height
        def no_query(*args,**kwargs):raise AssertionError('Resizing triggered a database operation')
        with monkeypatch.context() as context:
            context.setattr(case,'operation',no_query)
            tree.setColumnWidth(2,500);settle(qt_application,window)
            smaller=tree.visualRect(window.model.index(0,2)).height()
            assert smaller<height
            assert smaller>=8*window.fontMetrics().height()
            assert tree.frozen.visualRect(window.model.index(0,1)).height()==smaller
        saved=View.from_json(window.view.to_json());assert saved.auto_row_height
        window.set_view(replace(saved,auto_row_height=False));settle(qt_application,window)
        assert tree.uniformRowHeights() and tree.frozen.uniformRowHeights() and tree.right_frozen.uniformRowHeights()
        assert tree.visualRect(window.model.index(0,2)).height()<smaller
        assert not errors
    finally:settle(qt_application,window);window.close()


def test_xml_heights_and_dialog_roundtrip_preserve_defaults(tmp_path,qt_application):
    path=tmp_path/'height.layout'
    path.write_text('''<XtraSerializer><property name="OptionsView"><property name="RowAutoHeight">true</property></property><property name="RowHeight">36</property><property name="GroupRowHeight">48</property><property name="ColumnPanelRowHeight">52</property><property name="Columns"><property name="Item1"><property name="FieldName">Value</property></property></property><property name="Appearance"><property name="Row"><property name="TextOptions"><property name="WordWrap">Wrap</property></property></property></property></XtraSerializer>''')
    view=read_tle_layout(path,['Value']).view
    assert (view.auto_row_height,view.row_height,view.group_row_height,view.header_height)==(True,36,48,52)
    dialog=RowHeightDialog(view)
    try:
        dialog.accept();assert dialog.result()==1 and dialog.view==view
    finally:dialog.deleteLater()
    dialog=RowHeightDialog(View())
    try:
        dialog.auto.setChecked(True);dialog.accept()
        assert dialog.view.auto_row_height and dialog.view.layout_styles['row']['word_wrap']
    finally:dialog.deleteLater()
    for name,value in [('RowHeight','-2'),('GroupRowHeight','10001'),('ColumnPanelRowHeight','0')]:
        path.write_text(f'<XtraSerializer><property name="{name}">{value}</property></XtraSerializer>')
        with pytest.raises(ValueError):read_tle_layout(path,['Value'])


def test_fixed_group_row_and_header_heights_match_pinned_views(qt_application,tmp_path):
    source=tmp_path/'fixed.csv';source.write_text('Group,N\nA,1\nA,2\n')
    case=Case(tmp_path/'fixed.timeline');case.import_csv(source)
    view=View(groups=[0],row_height=36,group_row_height=48,header_height=52,right_pinned_columns=[1])
    window=Window(require_case=False);errors=[];window.error=errors.append
    try:
        window.attach(case,view);window.show();settle(qt_application,window)
        parent=window.model.index(0,0);window.tree.setExpanded(parent,True);settle(qt_application,window)
        assert window.tree.visualRect(parent.siblingAtColumn(1)).height()==48
        assert window.tree.right_frozen.visualRect(parent.siblingAtColumn(2)).height()==48
        child=window.model.index(0,1,parent)
        assert window.tree.visualRect(child).height()==36
        assert window.tree.right_frozen.visualRect(child.siblingAtColumn(2)).height()==36
        assert window.tree.header().height()>=52 and window.tree.right_frozen.header().height()==window.tree.header().height()
        assert not window.tree.uniformRowHeights()
        assert not errors
    finally:settle(qt_application,window);window.close()
