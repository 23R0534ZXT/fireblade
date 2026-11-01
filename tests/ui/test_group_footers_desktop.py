import time
from dataclasses import replace
from decimal import Decimal

import pytest
from PySide6.QtCore import QModelIndex,Qt
from PySide6.QtGui import QColor,QImage,QPainter
from PySide6.QtWidgets import QStyleOptionViewItem

from fireblade.core.engine import Case
from fireblade.core.models import Summary,View,Filter
from fireblade.core.settings import Settings
from fireblade.ui.app import Window
from fireblade.ui.exploration_dialogs import GroupsDialog


def settle(app,window):
    end=time.monotonic()+15
    while time.monotonic()<end:
        app.processEvents()
        if not window.jobs and not window.pool.activeThreadCount() and not window.model.jobs:return
        time.sleep(.005)
    raise AssertionError('Desktop did not settle')


def open_window(tmp_path,source_text,view):
    source=tmp_path/'s.csv';source.write_text(source_text)
    case=Case(tmp_path/'s.timeline',settings=Settings(page_size=25,max_loaded_rows=25));case.import_csv(source)
    window=Window(settings=case.settings);errors=[];window.error=errors.append
    window.attach(case,view);window.show()
    return window,errors


def test_group_and_global_footer_aggregates_pixels_pins_and_view_restore(qt_application,tmp_path):
    view=View(groups=[0],group_order='value',group_descending=False,group_footer_mode='always',right_pinned_columns=[1],
        summaries=[Summary(1,'sum',footer_column=1)],total_summaries=[Summary(1,'avg')],layout_styles={'group_footer':{'background':'#123456','foreground':'#ffffff'},'footer_panel':{'background':'#abcdef'}})
    window,errors=open_window(tmp_path,'Group,N\nA,2\nA,4\nB,100\n',view)
    try:
        settle(qt_application,window)
        assert window.model.rowCount()==4
        assert 'avg(N)=' in window.count_label.text() and float(window.count_label.text().split('avg(N)=')[1])==pytest.approx(106/3)
        footer=window.model.index(1,2)
        assert window.model.node(footer).footer and footer.data()=='sum=6.0000000000'
        assert not window.model.flags(footer)&Qt.ItemIsSelectable
        assert not window.model.hasChildren(footer.siblingAtColumn(0))
        assert not window.model.node(footer).children
        assert window.model.index(1,0).data().startswith('Total Group : A')
        for tree in (window.tree,window.tree.right_frozen):
            image=QImage(220,32,QImage.Format_ARGB32);image.fill(Qt.white)
            option=QStyleOptionViewItem();option.rect=image.rect();painter=QPainter(image)
            try:tree.itemDelegate().paint(painter,option,footer)
            finally:painter.end()
            assert image.pixelColor(180,2).name()=='#123456'
        assert window.count_label.grab().toImage().pixelColor(1,1).name()=='#abcdef'
        header=window.model.index(0,0);window.tree.setExpanded(header,True);settle(qt_application,window)
        assert window.model.rowCount(header)==2  # no duplicate child footer in always mode
        assert window.tree.right_frozen.visualRect(footer).height()==window.tree.visualRect(footer.siblingAtColumn(1)).height()
        dialog=GroupsDialog(window.case.headers,window.view)
        try:
            dialog.accept();assert dialog.result()==1 and dialog.view==window.view
        finally:dialog.deleteLater()
        saved=View.from_json(window.view.to_json());window.set_view(View());settle(qt_application,window)
        assert not any(node.footer for node in window.model.root.children)
        window.set_view(saved);settle(qt_application,window)
        assert window.model.node(window.model.index(1,0)).footer
        filtered=replace(saved,filters=[Filter(1,'le','4')]);window.set_view(filtered);settle(qt_application,window)
        assert window.model.rowCount()==2 and 'avg(N)=3.0' in window.count_label.text()
        assert not errors
    finally:settle(qt_application,window);window.close()


def test_expanded_footer_waits_for_last_page_and_does_not_affect_offsets(qt_application,tmp_path):
    text='Group,N\n'+''.join(f'A,{i}\n' for i in range(50))
    view=View(groups=[0],group_footer_mode='expanded',summaries=[Summary(1,'sum',footer_column=1)])
    window,errors=open_window(tmp_path,text,view)
    try:
        settle(qt_application,window);parent=window.model.index(0,0)
        assert window.model.rowCount()==1
        window.tree.setExpanded(parent,True);settle(qt_application,window)
        assert window.model.rowCount(parent)==25 and not any(n.footer for n in window.model.node(parent).children)
        window.model.fetchMore(parent);settle(qt_application,window)
        assert window.model.node(parent).offset==25 and window.model.rowCount(parent)==25
        window.model.fetchMore(parent);settle(qt_application,window)
        children=window.model.node(parent).children
        assert len(children)==26 and children[-1].footer
        assert [node.values[0] for node in children[:-1]]==list(range(26,51))
        assert children[-1].values[2]==Decimal(1225)
        window.model.fetchMore(parent);settle(qt_application,window)
        assert len(children)==26
        window.model.previous(parent);settle(qt_application,window)
        assert window.model.node(parent).offset==0
        assert [n.values[0] for n in window.model.node(parent).children]==list(range(1,26))
        window.tree.setExpanded(parent,False);settle(qt_application,window)
        assert not window.model.node(parent).children
        assert not errors
    finally:settle(qt_application,window);window.close()


def test_always_footers_do_not_skip_groups_when_windows_are_evicted(qt_application,tmp_path):
    text='Group,N\n'+''.join(f'g{i:03},{i}\n' for i in range(60))
    view=View(groups=[0],group_footer_mode='always',group_order='value',group_descending=False,summaries=[Summary(1,'sum',footer_column=1)])
    window,errors=open_window(tmp_path,text,view)
    try:
        settle(qt_application,window);seen=[]
        for page in range(3):
            nodes=window.model.root.children
            assert all(nodes[i+1].footer and nodes[i].path==nodes[i+1].path for i in range(0,len(nodes),2))
            seen += [node.path[0] for node in nodes if not node.footer]
            if page<2:window.model.fetchMore();settle(qt_application,window)
        assert seen==[f'g{i:03}' for i in range(60)]
        assert window.model.root.offset==50
        window.model.previous();settle(qt_application,window)
        assert window.model.root.offset==25
        assert [n.path[0] for n in window.model.root.children if not n.footer]==[f'g{i:03}' for i in range(25,50)]
        window.set_view(replace(view,expand_all=True));settle(qt_application,window)
        assert len(window.model.root.children)==25
        window.model.fetchMore();settle(qt_application,window)
        assert window.model.root.offset==25  # disk positions include footers
        assert not errors
    finally:settle(qt_application,window);window.close()
