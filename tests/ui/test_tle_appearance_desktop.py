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
