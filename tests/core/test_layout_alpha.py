from dataclasses import replace

import pytest
from PySide6.QtGui import QColor

from fireblade.core.models import FormatRule,View
from fireblade.core.rule_store import RuleBook
from fireblade.core.tle_appearance import validate_styles
from fireblade.core.tle_layout import color,read_tle_layout
from fireblade.ui.visual_rules import contrast_color,visual_value


@pytest.mark.parametrize('raw,expected',[
    ('128, 255, 0, 0','#80ff0000'),('0, 12, 34, 56','#000c2238'),
    ('255, 12, 34, 56','#0c2238'),('12, 34, 56','#0c2238'),
    ('#80112233','#80112233'),
])
def test_argb_color_keeps_alpha_without_flattening(raw,expected):
    warnings=[]
    assert color(raw,'#ffffff',warnings)==expected
    assert not warnings
    validate_styles({'row':{'background':expected}},1)


def test_alpha_import_view_global_rules_and_editor_fields_roundtrip(tmp_path):
    path=tmp_path/'alpha.layout'
    path.write_text('''<XtraSerializer><property name="Columns"><property name="Item1"><property name="FieldName">Value</property></property></property>
    <property name="Appearance"><property name="Row"><property name="BackColor">128, 255, 0, 0</property><property name="BackColor2">64, 0, 0, 255</property><property name="BorderColor">32, 0, 255, 0</property></property></property>
    <property name="FormatRules"><property name="Item1"><property name="RuleType">#FormatConditionRuleExpression</property><property name="Rule"><property name="Expression">[Value]='1'</property><property name="Appearance"><property name="BackColor">128, 0, 0, 255</property><property name="ForeColor">192, 255, 255, 255</property></property></property></property></property></XtraSerializer>''')
    layout=read_tle_layout(path,['Value'])
    assert not layout.warnings
    assert layout.view.layout_styles['row']==dict(background='#80ff0000',background2='#400000ff',gradient='Horizontal',border_color='#2000ff00')
    rule=layout.view.format_rules[0]
    assert rule.background=='#800000ff' and rule.foreground=='#c0ffffff'
    assert View.from_json(layout.view.to_json())==layout.view
    assert RuleBook.from_bytes(RuleBook(['Value'],[rule]).to_bytes()).rules==[rule]


def test_graphic_interpolation_keeps_alpha_and_contrast_uses_actual_base():
    rule=FormatRule(target=0,visual='scale',background='#00ff0000',foreground='#800000ff')
    assert visual_value(rule,'0')[2].alpha()==0
    assert visual_value(rule,'50')[2].getRgb()==(128,0,128,64)
    assert visual_value(rule,'100')[2].getRgb()==(0,0,255,128)
    assert contrast_color(QColor('#00ffffff'),QColor('#101010')).name()=='#ffffff'
    assert contrast_color(QColor('#00000000'),QColor('#ffffff')).name()=='#000000'
    assert contrast_color(QColor('#80ffffff'),QColor('#000000')).name()=='#000000'
    for invalid in ('#12345','#1234567','#123456789','#gg112233'):
        with pytest.raises(ValueError):RuleBook(['Value'],[replace(rule,background=invalid)]).validate()
