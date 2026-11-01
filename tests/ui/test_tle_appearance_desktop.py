import time
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush,QFontMetrics
from PySide6.QtWidgets import QApplication,QStyle,QStyleOptionViewItem
from fireblade.core.engine import Case
from fireblade.core.models import View
from fireblade.core.tle_layout import read_tle_layout
from fireblade.ui.app import Window


def settle(app,w):
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        app.processEvents()
        if not w.jobs and not w.pool.activeThreadCount() and not w.model.jobs:return
        time.sleep(.005)
    raise AssertionError('UI did not settle')


def test_row_column_header_and_selection_styles_render_and_persist(qt_application,tmp_path):
    source=tmp_path/'s.csv';source.write_text('User,Value\nalice,1\nbob,2\n')
    case=Case(tmp_path/'s.timeline');case.import_csv(source)
    path=tmp_path/'styles.layout'
    path.write_text('''<XtraSerializer>
      <property name="OptionsView"><property name="EnableAppearanceOddRow">true</property><property name="EnableAppearanceEvenRow">true</property></property>
      <property name="Appearance">
       <property name="Row"><property name="ForeColor">Blue</property><property name="Font">Arial, 11pt, style=Italic</property></property>
       <property name="OddRow"><property name="BackColor">#ffeedd</property></property>
       <property name="EvenRow"><property name="BackColor">#ddeeff</property></property>
       <property name="SelectedRow"><property name="BackColor">#112233</property><property name="ForeColor">White</property></property>
       <property name="HeaderPanel"><property name="BackColor">#123456</property><property name="ForeColor">White</property><property name="Font">Arial, 13pt, style=Bold</property></property>
      </property>
      <property name="Columns">
       <property name="Item1"><property name="FieldName">User</property><property name="VisibleIndex">0</property><property name="AppearanceCell"><property name="ForeColor">Green</property><property name="TextOptions"><property name="HAlignment">Far</property></property></property></property>
       <property name="Item2"><property name="FieldName">Value</property><property name="Fixed">Right</property><property name="VisibleIndex">1</property><property name="AppearanceHeader"><property name="BackColor">#654321</property><property name="Font">Arial, 18pt</property></property></property>
      </property></XtraSerializer>''')
    layout=read_tle_layout(path,case.headers);w=Window();errors=[];w.error=errors.append
    try:
        w.attach(case);w.apply_tle_layout(layout);w.show();settle(qt_application,w)
        first=w.model.index(0,1);second=w.model.index(1,1)
        assert first.data(Qt.BackgroundRole).name()=='#ffeedd' and second.data(Qt.BackgroundRole).name()=='#ddeeff'
        assert first.data(Qt.ForegroundRole).name()=='#008000' and first.data(Qt.FontRole).italic()
        assert first.data(Qt.TextAlignmentRole)&Qt.AlignRight
        assert w.model.headerData(1,Qt.Horizontal,Qt.BackgroundRole).name()=='#123456'
        assert w.model.headerData(2,Qt.Horizontal,Qt.BackgroundRole).name()=='#654321'
        assert w.tree.header().height()>=QFontMetrics(w.model.headerData(2,Qt.Horizontal,Qt.FontRole)).height()+8
        assert w.tree.right_frozen.header().height()==w.tree.header().height()
        for panel,section,color in [(w.tree,1,'#123456'),(w.tree.right_frozen,2,'#654321')]:
            header=panel.header();QApplication.processEvents();image=header.viewport().grab().toImage()
            assert image.pixelColor(header.sectionViewportPosition(section)+8,3).name()==color
        option=QStyleOptionViewItem();option.state|=QStyle.State_Selected
        w.tree.itemDelegate().initStyleOption(option,first)
        assert option.backgroundBrush.color().name()=='#112233'
        assert View.from_json(w.view.to_json()).layout_styles==layout.view.layout_styles
        w.save_format_layout()
        from fireblade.core.auto_layout import load_auto_layout
        assert load_auto_layout(case.headers,case.info)[0].view.layout_styles==layout.view.layout_styles
        assert not errors
    finally:settle(qt_application,w);w.close()


def test_conditional_presets_merge_explicit_overrides_and_gradients(tmp_path):
    path=tmp_path/'conditional.layout'
    path.write_text('''<XtraSerializer><property name="Columns"><property name="Item1"><property name="FieldName">Value</property></property></property>
    <property name="FormatRules"><property name="Item1"><property name="RuleType">#FormatConditionRuleExpression</property><property name="Rule"><property name="Expression">[Value]='1'</property><property name="PredefinedName">Red Bold Text</property><property name="Appearance"><property name="BackColor">#ffffff</property><property name="BackColor2">#000000</property><property name="GradientMode">Vertical</property><property name="Options"><property name="UseFont">false</property></property><property name="TextOptions"><property name="HAlignment">Far</property></property></property></property></property></property></XtraSerializer>''')
    view=read_tle_layout(path,['Value']).view;rule=view.format_rules[0]
    assert rule.foreground=='#9c0006' and rule.use_foreground and not rule.use_font
    assert rule.appearance==dict(background2='#000000',gradient='Vertical',horizontal='Far')
    source=tmp_path/'s.csv';source.write_text('Value\n1\n2\n')
    case=Case(tmp_path/'s.timeline');case.import_csv(source)
    w=Window();errors=[];w.error=errors.append
    try:
        w.attach(case,view);settle(QApplication.instance(),w)
        brush=w.model.index(0,1).data(Qt.BackgroundRole)
        assert isinstance(brush,QBrush) and [c.name() for _,c in brush.gradient().stops()]==['#ffffff','#000000']
        assert w.model.index(0,1).data(Qt.TextAlignmentRole)&Qt.AlignRight
        assert not errors
    finally:settle(QApplication.instance(),w);w.close()


def raster():
    import base64
    from PySide6.QtCore import QByteArray,QBuffer,QIODevice
    from PySide6.QtGui import QImage,QColor
    image=QImage(10,10,QImage.Format_ARGB32);image.fill(QColor('#fe12ab'))
    data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.WriteOnly);assert image.save(buffer,'PNG')
    return base64.b64encode(bytes(data)).decode()


def test_embedded_images_borders_wrapping_and_panels_really_render(qt_application,tmp_path):
    source=tmp_path/'s.csv';source.write_text('User,Value\nalice has a long multiline forensic description,1\nbob,2\n')
    case=Case(tmp_path/'s.timeline');case.import_csv(source)
    encoded=raster();path=tmp_path/'images.layout'
    path.write_text(f'''<XtraSerializer><property name="Appearance">
     <property name="GroupPanel"><property name="BackColor">#102030</property><property name="ForeColor">White</property><property name="BorderColor">#ff0000</property><property name="Image">{encoded}</property><property name="ImageAlignment">TopRight</property></property>
     <property name="FooterPanel"><property name="BackColor">#405060</property></property>
     <property name="ViewCaption"><property name="ForeColor">Blue</property></property>
     <property name="Empty"><property name="BackColor">#aabbcc</property><property name="Image">{encoded}</property></property>
     <property name="Row"><property name="TextOptions"><property name="WordWrap">Wrap</property></property></property>
     <property name="HeaderPanel"><property name="BackColor">White</property><property name="BorderColor">#ff0000</property><property name="ImageOptions"><property name="Image">{encoded}</property></property><property name="ImageAlignment">TopRight</property></property>
     </property><property name="Columns">
     <property name="Item1"><property name="FieldName">User</property><property name="Width">160</property><property name="AppearanceCell"><property name="BorderColor">#00ff00</property><property name="Image">{encoded}</property><property name="ImageAlignment">TopRight</property></property></property>
     <property name="Item2"><property name="FieldName">Value</property><property name="Fixed">Right</property></property>
     </property></XtraSerializer>''')
    layout=read_tle_layout(path,case.headers);assert not layout.warnings
    w=Window();errors=[];w.error=errors.append
    try:
        w.attach(case);w.apply_tle_layout(layout);w.show();settle(qt_application,w)
        panel=w.groups_label.grab().toImage()
        assert panel.pixelColor(1,4).name()=='#102030'
        assert panel.pixelColor(0,0).name()=='#ff0000'
        assert panel.pixelColor(panel.width()-3,3).name()=='#fe12ab'
        assert w.count_label.grab().toImage().pixelColor(1,1).name()=='#405060'
        for tree,col in [(w.tree,1),(w.tree.right_frozen,2)]:
            header=tree.header();image=header.viewport().grab().toImage();x=header.sectionViewportPosition(col)+header.sectionSize(col)-3
            assert image.pixelColor(x,3).name()=='#fe12ab'
            assert image.pixelColor(x,0).name()=='#ff0000'
        index=w.model.index(0,1);rect=w.tree.visualRect(index)
        assert rect.height()>=3*w.fontMetrics().height()
        image=w.tree.viewport().grab().toImage()
        assert image.pixelColor(rect.right()-4,rect.top()+4).name()=='#fe12ab'
        assert image.pixelColor(rect.left(),rect.top()+5).name()=='#00ff00'
        assert w.tree.right_frozen.visualRect(w.model.index(0,2)).height()==rect.height()
        saved=View.from_json(w.view.to_json());assert saved.layout_styles==layout.view.layout_styles
        w.set_view(View());settle(qt_application,w)
        assert not w.groups_label._tle_appearance.appearance
        assert w.tree.visualRect(w.model.index(0,1)).height()<rect.height()
        w.set_view(saved);settle(qt_application,w)
        w.search.setText('no such record');w.apply();settle(qt_application,w)
        image=w.tree.viewport().grab().toImage();assert image.pixelColor(4,4).name()=='#aabbcc'
        assert image.pixelColor(image.width()//2,image.height()//2).name()=='#fe12ab'
        assert not errors
    finally:settle(qt_application,w);w.close()


def test_custom_named_styles_are_flattened_and_conditional_images_render(qt_application,tmp_path):
    import json
    from fireblade.core.layout import write_json,read_layout
    source=tmp_path/'s.csv';source.write_text('Value\n1\n2\n');case=Case(tmp_path/'s.timeline');case.import_csv(source)
    path=tmp_path/'custom.layout';encoded=raster()
    path.write_text('''<XtraSerializer><property name="Columns"><property name="Item1"><property name="FieldName">Value</property></property></property><property name="FormatRules"><property name="Item1"><property name="RuleType">#FormatConditionRuleExpression</property><property name="Rule"><property name="Expression">[Value]='1'</property><property name="PredefinedName">Evidence</property><property name="Appearance"><property name="ForeColor">Blue</property></property></property></property></property></XtraSerializer>''')
    sidecar=Path(str(path)+'.styles.json');sidecar.write_text(json.dumps({'Evidence':dict(background='#abcdef',foreground='#112233',border_color='#00ff00',image=encoded,image_align='TopRight',word_wrap=True)}))
    layout=read_tle_layout(path,case.headers);assert not layout.warnings
    rule=layout.view.format_rules[0];assert rule.foreground=='#0000ff' and rule.background=='#abcdef' and rule.appearance['image']==encoded
    dest=tmp_path/'saved.fireblade-view';write_json(dest,dict(format='fireblade-view',version=1,headers=case.headers,view=json.loads(layout.view.to_json())));sidecar.unlink()
    restored=read_layout(dest,case.headers);assert restored.format_rules[0].appearance==rule.appearance
    w=Window();errors=[];w.error=errors.append
    try:
        w.attach(case,restored);w.show();settle(qt_application,w)
        first=w.model.index(0,1);second=w.model.index(1,1)
        assert first.data(Qt.BackgroundRole).name()=='#abcdef'
        image=w.tree.viewport().grab().toImage();rect=w.tree.visualRect(first)
        assert image.pixelColor(rect.right()-4,rect.top()+4).name()=='#fe12ab'
        assert image.pixelColor(rect.left(),rect.top()+5).name()=='#00ff00'
        assert w.tree.itemDelegate().appearance(second,QStyleOptionViewItem())=={}
        assert not errors
    finally:settle(qt_application,w);w.close()


def test_search_filters_and_detail_controls_show_panel_styles_and_reset(qt_application,tmp_path):
    source=tmp_path/'s.csv';source.write_text('Value\n1\n');case=Case(tmp_path/'s.timeline');case.import_csv(source)
    encoded=raster();view=View(layout_styles={
        'find_panel':dict(background='#123456',foreground='#abcdef',border_color='#00ff00',image=encoded,image_align='TopRight'),
        'preview':dict(background='#654321',foreground='#fedcba',image=encoded,image_align='TopRight'),
        'filter_panel':dict(background='#334455',foreground='#ffffff',word_wrap=True),
    })
    w=Window();errors=[];w.error=errors.append
    try:
        w.attach(case,view);w.show();settle(qt_application,w)
        w.search.clearFocus();qt_application.processEvents()
        search=w.search.grab().toImage()
        assert search.pixelColor(3,3).name()=='#123456'
        assert search.pixelColor(0,0).name()=='#00ff00'
        assert search.pixelColor(search.width()-5,4).name()=='#fe12ab'
        detail=w.details.viewport().grab().toImage()
        assert detail.pixelColor(3,3).name()=='#654321'
        assert detail.pixelColor(detail.width()-3,3).name()=='#fe12ab'
        assert w.filters.wordWrap()
        w.set_view(View());settle(qt_application,w)
        assert not w.search.styleSheet() and not w.details.styleSheet() and not w.filters.wordWrap()
        assert not errors
    finally:settle(qt_application,w);w.close()


def test_standalone_mixed_icon_acceptance_runs_against_real_widgets(qt_application,tmp_path):
    from fireblade.validation.layout_appearance import check_mixed_icon_layout
    source=tmp_path/'s.csv';source.write_text('ID,User\n9007199254740993,alice\n1,bob\n5,alice\n')
    case=Case(tmp_path/'s.timeline');case.import_csv(source)
    window=Window();errors=[];window.error=errors.append
    def expect(value,message):assert value,message
    try:
        window.attach(case);window.show();settle(qt_application,window)
        check_mixed_icon_layout(window,tmp_path,lambda:settle(qt_application,window),expect)
        assert not errors
    finally:settle(qt_application,window);window.close()


def test_high_priority_appearance_overrides_per_property_and_resets(qt_application,tmp_path):
    from dataclasses import replace
    from PySide6.QtGui import QImage,QPainter,QColor
    from fireblade.core.models import FormatRule
    from fireblade.core.rule_store import RuleBook
    source=tmp_path/'s.csv';source.write_text('Value\n1\n2\n');case=Case(tmp_path/'s.timeline');case.import_csv(source)
    rule=FormatRule(target=0,background='#0000ff',foreground='#ffffff',use_font=False)
    view=View(format_rules=[rule],right_pinned_columns=[0],layout_styles={
        'row':dict(background='#aabbcc',high_priority=True),
        'cell:0':dict(background='#00ff00',foreground='#112233'),
        'selected_row':dict(background='#ffff00'),
        'header':dict(background='#123456',high_priority=True),
        'header:0':dict(background='#654321'),
    })
    window=Window();errors=[];window.error=errors.append
    try:
        window.attach(case,view);window.show();settle(qt_application,window)
        index=window.model.index(0,1)
        assert index.data(Qt.BackgroundRole).name()=='#aabbcc'
        assert index.data(Qt.ForegroundRole).name()=='#ffffff'  # priority only affects specified properties
        tree=window.tree.right_frozen;delegate=tree.itemDelegate()
        option=QStyleOptionViewItem();option.rect=tree.visualRect(index);option.state|=QStyle.State_Selected
        delegate.initStyleOption(option,index)
        assert option.backgroundBrush.color().name()=='#aabbcc'
        image=QImage(220,32,QImage.Format_ARGB32);image.fill(Qt.white)
        paint_option=QStyleOptionViewItem();paint_option.rect=image.rect();paint_option.state|=QStyle.State_Selected
        painter=QPainter(image)
        try:delegate.paint(painter,paint_option,index)
        finally:painter.end()
        assert image.pixelColor(180,5).name()=='#aabbcc'
        header=tree.header();raster=header.viewport().grab().toImage();x=header.sectionViewportPosition(1)+8
        assert raster.pixelColor(x,3).name()=='#123456'
        # A later high-priority column overrides an earlier high-priority row.
        saved=View.from_json(window.view.to_json());saved.layout_styles['cell:0']['high_priority']=True
        window.set_view(saved);settle(qt_application,window)
        assert window.model.index(0,1).data(Qt.BackgroundRole).name()=='#00ff00'
        # A high-priority conditional rule participates in the same ordering.
        saved.format_rules=[replace(rule,appearance={'high_priority':True})]
        assert RuleBook.from_bytes(RuleBook(case.headers,saved.format_rules).to_bytes()).rules==saved.format_rules
        window.set_view(saved);settle(qt_application,window)
        assert window.model.index(0,1).data(Qt.BackgroundRole).name()=='#0000ff'
        window.set_view(View(format_rules=[rule]));settle(qt_application,window)
        option=QStyleOptionViewItem();option.state|=QStyle.State_Selected
        window.tree.itemDelegate().initStyleOption(option,window.model.index(0,1))
        assert option.state & QStyle.State_Selected  # default Qt selection restored
        assert window.model.index(0,1).data(Qt.BackgroundRole).name()=='#0000ff'
        assert not errors
    finally:settle(qt_application,window);window.close()


def test_standalone_priority_acceptance_runs_against_real_widgets(qt_application,tmp_path):
    from fireblade.validation.layout_appearance import check_priority_layout
    source=tmp_path/'s.csv';source.write_text('ID,User\n1,alice\n2,bob\n')
    case=Case(tmp_path/'s.timeline');case.import_csv(source)
    window=Window();errors=[];window.error=errors.append
    def expect(value,message):assert value,message
    try:
        window.attach(case);window.show();settle(qt_application,window)
        check_priority_layout(window,tmp_path,lambda:settle(qt_application,window),expect)
        assert not errors
    finally:settle(qt_application,window);window.close()
