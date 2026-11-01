import time

import pytest
from PySide6.QtCore import Qt,QPoint
from PySide6.QtGui import QColor,QImage,QPainter,QPalette
from PySide6.QtWidgets import QStyle,QStyleOptionViewItem

from fireblade.core.engine import Case
from fireblade.core.models import View
from fireblade.core.tle_layout import read_tle_layout
from fireblade.ui.app import Window
from fireblade.ui.advanced_dialogs import RulesDialog
from fireblade.ui.theme import apply_theme
from fireblade.ui.visual_rules import contrast_color


def settle(app,window):
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        app.processEvents()
        if not window.jobs and not window.pool.activeThreadCount() and not window.model.jobs:return
        time.sleep(.005)
    raise AssertionError('Desktop did not settle')


def composite(color,base):
    # Let the raster engine provide an independent compositing reference.
    image=QImage(1,1,QImage.Format_ARGB32);image.fill(base)
    painter=QPainter(image);painter.fillRect(image.rect(),color);painter.end()
    return image.pixelColor(0,0)


@pytest.mark.parametrize('theme',['light','dark'])
def test_argb_pixels_in_grid_pins_header_selection_and_restored_view(qt_application,tmp_path,theme):
    source=tmp_path/'s.csv';source.write_text('Value\n1\n2\n')
    case=Case(tmp_path/'s.timeline');case.import_csv(source)
    xml=tmp_path/'alpha.layout';xml.write_text('''<XtraSerializer><property name="Columns"><property name="Item1"><property name="FieldName">Value</property><property name="Fixed">Right</property></property></property>
      <property name="Appearance"><property name="Row"><property name="BackColor">128, 255, 0, 0</property></property><property name="HeaderPanel"><property name="BackColor">128, 0, 255, 0</property></property><property name="SelectedRow"><property name="BackColor">128, 0, 255, 0</property></property></property>
      <property name="FormatRules"><property name="Item1"><property name="RuleType">#FormatConditionRuleExpression</property><property name="Rule"><property name="Expression">[Value]='2'</property><property name="Appearance"><property name="BackColor">128, 0, 0, 255</property></property></property></property></property></XtraSerializer>''')
    layout=read_tle_layout(xml,case.headers);window=Window();errors=[];window.error=errors.append
    try:
        window.attach(case,layout.view);window.preferences.theme=theme;window.apply_preferences()
        window.show();settle(qt_application,window);window.tree.clearSelection();window.tree.clearFocus();qt_application.processEvents()
        base=qt_application.palette().color(QPalette.Base)
        for row,encoded in [(0,'#80ff0000'),(1,'#800000ff')]:
            index=window.model.index(row,1);raw=index.data(Qt.BackgroundRole)
            assert raw.alpha()==128 and raw.name(QColor.HexArgb)==encoded
            assert index.data(Qt.ForegroundRole)==contrast_color(raw,base)
            tree=window.tree.right_frozen;rect=tree.visualRect(index);image=tree.viewport().grab().toImage()
            actual=image.pixelColor(rect.right()-6,rect.top()+5)
            row_base=qt_application.palette().color(QPalette.AlternateBase if row%2 else QPalette.Base)
            assert actual==composite(raw,row_base)
            # The central delegate must composite identically to the pinned one.
            image=QImage(220,32,QImage.Format_ARGB32);image.fill(row_base)
            option=QStyleOptionViewItem();option.rect=image.rect()
            if row%2:option.features|=QStyleOptionViewItem.Alternate
            window.tree.itemDelegate().initStyleOption(option,index)
            assert option.palette.color(QPalette.Text)==contrast_color(raw,row_base)
            painter=QPainter(image)
            try:window.tree.itemDelegate().paint(painter,option,index)
            finally:painter.end()
            assert image.pixelColor(180,5)==composite(raw,row_base)
        index=window.model.index(0,1)
        image=QImage(220,32,QImage.Format_ARGB32);image.fill(base)
        option=QStyleOptionViewItem();option.rect=image.rect();option.state|=QStyle.State_Selected
        painter=QPainter(image)
        try:window.tree.itemDelegate().paint(painter,option,index)
        finally:painter.end()
        assert image.pixelColor(180,5)==composite(QColor('#8000ff00'),base)
        header=window.tree.right_frozen.header();image=QImage(220,32,QImage.Format_ARGB32)
        header_base=header.palette().color(QPalette.Button);image.fill(header_base)
        painter=QPainter(image)
        try:header.paintSection(painter,image.rect(),1)
        finally:painter.end()
        assert image.pixelColor(180,5)==composite(QColor('#8000ff00'),header_base)
        dialog=RulesDialog(case.headers,window.view.format_rules,window)
        try:
            dialog.accept();assert dialog.result()==1 and dialog.rules==window.view.format_rules
        finally:dialog.deleteLater()
        saved=View.from_json(window.view.to_json());window.set_view(View());settle(qt_application,window)
        window.set_view(saved);settle(qt_application,window)
        assert window.model.index(0,1).data(Qt.BackgroundRole).alpha()==128
        assert not errors
    finally:
        settle(qt_application,window);window.close();apply_theme(qt_application)


@pytest.mark.parametrize('theme',['light','dark'])
def test_transparent_panel_and_edit_controls_composite_once(qt_application,tmp_path,theme):
    source=tmp_path/'s.csv';source.write_text('Value\n1\n')
    case=Case(tmp_path/'s.timeline');case.import_csv(source)
    view=View(layout_styles={'group_panel':{'background':'#80ff0000'},'footer_panel':{'background':'#8000ff00'},'find_panel':{'background':'#800000ff'},'preview':{'background':'#8000ff00'}})
    window=Window();errors=[];window.error=errors.append
    try:
        window.attach(case,view);window.preferences.theme=theme;window.apply_preferences();window.show();settle(qt_application,window)
        for widget,encoded in [(window.groups_label,'#80ff0000'),(window.count_label,'#8000ff00'),(window.search,'#800000ff'),(window.details.viewport(),'#8000ff00')]:
            raster=window.grab().toImage();point=widget.mapTo(window,QPoint(4,4))
            base=window.palette().color(QPalette.Window)
            assert raster.pixelColor(point)==composite(QColor(encoded),base),(widget,raster.pixelColor(point).name(),composite(QColor(encoded),base).name())
        assert not errors
    finally:settle(qt_application,window);window.close();apply_theme(qt_application)
