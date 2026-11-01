"""Acceptance checks for separate group/global footers in the real EXE."""
import csv
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage,QPainter
from PySide6.QtWidgets import QStyleOptionViewItem

from fireblade.core.models import View
from fireblade.core.tle_layout import read_tle_layout
from fireblade.ui.exploration_dialogs import GroupsDialog


def check_group_footers(window,directory,settle,expect,captures=None):
    directory=Path(directory)
    path=directory/'separate-footers.layout'
    path.write_text('''<XtraSerializer>
      <property name="OptionsView"><property name="GroupFooterShowMode">VisibleAlways</property><property name="ShowFooter">true</property></property>
      <property name="Columns"><property name="Item1"><property name="FieldName">Type</property><property name="GroupIndex">0</property><property name="SortOrder">Ascending</property></property>
      <property name="Item2"><property name="FieldName">ID</property><property name="Name">amount</property><property name="Fixed">Right</property></property></property>
      <property name="GroupSummary"><property name="Item1"><property name="FieldName">ID</property><property name="SummaryType">Sum</property><property name="ShowInGroupColumnFooterName">amount</property></property></property>
      <property name="TotalSummary"><property name="Item1"><property name="FieldName">ID</property><property name="SummaryType">Sum</property></property></property>
      <property name="Appearance"><property name="FooterPanel"><property name="BackColor">#abcdef</property></property><property name="GroupFooter"><property name="BackColor">#123456</property><property name="ForeColor">White</property></property></property>
      </XtraSerializer>''',encoding='utf-8')
    layout=read_tle_layout(path,window.case.headers)
    expect(not layout.warnings,'Unexpected group footer adaptation warning')
    window.apply_tle_layout(layout);settle()
    model=window.model;column=window.case.headers.index('ID')+1
    expect(model.rowCount()==4,'Collapsed groups are missing their own footers')
    footer=model.index(1,column)
    expect(model.node(footer).footer,'Group footer is not a separate model row')
    expect(Decimal(footer.data().split('=')[1])==9007199254740994,'Group footer sum lost exact integer precision')
    expect(Decimal(window.count_label.text().split('sum(ID)=')[1])==9007199254740999,'Global footer reused a group aggregate')
    expect(not model.flags(footer)&Qt.ItemIsSelectable and not model.hasChildren(footer.siblingAtColumn(0)),'A footer behaves like a forensic event or an expandable group')
    for tree in (window.tree,window.tree.right_frozen):
        image=QImage(220,32,QImage.Format_ARGB32);image.fill(Qt.white)
        option=QStyleOptionViewItem();option.rect=image.rect();painter=QPainter(image)
        try:tree.itemDelegate().paint(painter,option,footer)
        finally:painter.end()
        expect(image.pixelColor(2,2).name()=='#123456',f'Pinned/central group footer style is missing: {image.pixelColor(2,2).name()} / {footer.data(Qt.BackgroundRole).name()}')
    raster=window.count_label.grab().toImage()
    expect(raster.pixelColor(1,1).name()=='#abcdef','Global and group footers share their appearance')
    parent=model.index(0,0);window.tree.setExpanded(parent,True);settle()
    expect(model.rowCount(parent)==2,'Always-visible footer was duplicated inside the expanded group')
    saved=View.from_json(window.view.to_json())
    dialog=GroupsDialog(window.case.headers,window.view,window)
    try:
        dialog.accept()
        expect(dialog.result()==1 and dialog.view==window.view,'Editing the footer dialog lost imported summary placement or sorting')
    finally:dialog.deleteLater()
    target=directory/'footer-source-export.csv';window.case.export(target,saved)
    with target.open(encoding='utf-8-sig',newline='') as stream:
        expect(len(list(csv.reader(stream)))==4,'Footer rows leaked into the forensic source export')
    if captures:window.grab().save(str(Path(captures)/'separate-group-and-global-footers.png'))
    window.set_view(replace(saved,group_footer_mode='expanded'));settle()
    expect(window.model.rowCount()==2,'Expanded-only mode added collapsed footers')
    parent=window.model.index(0,0);window.tree.setExpanded(parent,True);settle()
    expect(window.model.rowCount(parent)==3 and window.model.node(window.model.index(2,0,parent)).footer,'Expanded-only group footer is not after its source rows')
    window.set_view(replace(saved,expand_all=True));settle()
    expect(sum(node.footer for node in window.model.root.children)==2,'Complete hierarchy lost its group footers')
    window.set_view(replace(saved,show_total_footer=False));settle()
    expect('sum(ID)' not in window.count_label.text(),'Global footer visibility was ignored')
    window.set_view(saved);settle()
    expect(window.model.node(window.model.index(1,0)).footer,'Restoring the view lost its footer mode')
