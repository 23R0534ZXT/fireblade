from pathlib import Path
import csv
import pytest
from fireblade.core.engine import Case
from fireblade.core.tle_layout import read_tle_layout
from fireblade.core.profile_catalog import CATALOG
from fireblade.core.profiles import detect_profile, profile_transformations

FIXTURES=Path(__file__).parents[1]/'fixtures'/'tle-layouts'


@pytest.mark.parametrize('name',['ForensicTimeline','SuperTimeline','EvtxECmd','HayabusaStandard'])
def test_official_plugin_layouts_migrate_with_real_control_names(name,tmp_path):
    definition=next(p for p in CATALOG if p['name']==name)
    source=tmp_path/'source.csv'
    with source.open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(definition['signature']);writer.writerow(['']*len(definition['signature']))
    case=Case(tmp_path/'source.timeline')
    try:
        case.import_csv(source)
        profile=detect_profile(case.headers)
        planned=profile_transformations(profile,case.headers)
        if planned:case.add_derived_columns(planned)
        layout=read_tle_layout(FIXTURES/(name+'.layout'),case.headers)
        assert layout.columns
        case.validate_view(layout.view)
        rows=case.page(layout.view)
        case.page_styles(layout.view,rows)
        if name=='ForensicTimeline':assert len(layout.view.format_rules)==29
        if name=='SuperTimeline':assert len(layout.view.format_rules)==7
    finally:case.close()


def test_layout_filter_rules_summaries_and_datetime_groups_execute(tmp_path):
    path=tmp_path/'test.layout'
    path.write_text('''<XtraSerializer>
    <property name="Columns"><property name="Item1"><property name="Name">colUser</property><property name="GroupIndex">0</property></property>
      <property name="Item2"><property name="FieldName">Size</property><property name="SortOrder">Descending</property><property name="SortIndex">0</property></property></property>
    <property name="ActiveFilterString">Upper([User]) = 'ALICE' And [Size] * 2 &gt;= 10</property>
    <property name="GroupSummary"><property name="Item1"><property name="FieldName">Size</property><property name="SummaryType">Sum</property></property></property>
    <property name="FormatRules"><property name="Item1"><property name="ApplyToRow">true</property><property name="RuleType">#FormatConditionRuleExpression</property><property name="Rule"><property name="Expression">[Size]&gt;5</property><property name="Appearance"><property name="BackColor">255, 0, 0</property><property name="ForeColor">White</property><property name="Font">Segoe UI, 10pt, style=Bold, Italic, Underline, Strikeout</property></property></property></property></property>
    </XtraSerializer>''')
    source=tmp_path/'s.csv';source.write_text('User,Size\nalice,4\nalice,7\nbob,8\n')
    case=Case(tmp_path/'s.timeline')
    try:
        case.import_csv(source);layout=read_tle_layout(path,case.headers)
        case.validate_view(layout.view)
        assert case.count(layout.view)==1
        assert str(case.page(layout.view)[0][2])=='7.0000000000'
        leaves=case.page(layout.view,('alice',))
        assert case.page_styles(layout.view,leaves)=={2:(0,)}
        assert layout.view.format_rules[0].foreground=='#ffffff'
        font_rule=layout.view.format_rules[0]
        assert font_rule.bold and font_rule.italic and font_rule.underline and font_rule.strikeout
    finally:case.close()


def test_untranslatable_expression_or_format_rule_is_never_silently_dropped(tmp_path):
    path=tmp_path/'test.layout'
    prefix='<XtraSerializer><property name="Columns"><property name="Item1"><property name="FieldName">ID</property></property></property>'
    for value in ('<property name="ActiveFilterString">Unknown([ID])</property>', '<property name="FormatRules"><property name="Item1"><property name="RuleType">#UnknownRule</property></property></property>'):
        path.write_text(prefix+value+'</XtraSerializer>')
        with pytest.raises(ValueError):read_tle_layout(path,['ID'])


def test_sigcheck_layout_boolean_filter_targets_converted_status(tmp_path):
    definition=next(p for p in CATALOG if p['name']=='Sigcheck')
    source=tmp_path/'sigcheck.csv'
    with source.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=definition['signature']);w.writeheader()
        verified=next(h for h in definition['signature'] if h.casefold()=='verified')
        w.writerow({verified:'Signed'});w.writerow({verified:'Unsigned'})
    case=Case(tmp_path/'s.timeline')
    try:
        case.import_csv(source)
        case.add_derived_columns(profile_transformations(detect_profile(case.headers),case.headers))
        path=tmp_path/'sigcheck.layout'
        path.write_text('<XtraSerializer><property name="Columns"><property name="Item1"><property name="Name">colVerified</property></property></property><property name="ActiveFilterString">[Verified] = True</property></XtraSerializer>')
        layout=read_tle_layout(path,case.headers)
        assert case.count(layout.view)==1
        assert layout.columns[0]['column']==case.headers.index('Fireblade_Bool_Verified')
        assert layout.columns[0]['column'] in layout.view.boolean_columns
    finally:case.close()


@pytest.mark.parametrize('kind,properties,expected', [
 ('TopBottom','<property name="TopBottom">Bottom</property><property name="Rank">1</property>',{1}),
 ('AboveBelowAverage','<property name="AverageType">Above</property>',{3}),
 ('UniqueDuplicate','<property name="UniqueDuplicate">Duplicate</property>',set()),
])
def test_statistical_layout_rules_execute(tmp_path,kind,properties,expected):
    path=tmp_path/'s.layout';path.write_text(f'''<XtraSerializer><property name="Columns"><property name="Item1"><property name="FieldName">Value</property></property></property><property name="FormatRules"><property name="Item1"><property name="ColumnName">Value</property><property name="RuleType">#FormatConditionRule{kind}</property><property name="Rule">{properties}<property name="Appearance"><property name="BackColor">Red</property></property></property></property></property></XtraSerializer>''')
    source=tmp_path/'s.csv';source.write_text('Value\n1\n3\n100\n');case=Case(tmp_path/'s.timeline')
    try:
        case.import_csv(source);view=read_tle_layout(path,case.headers).view;case.validate_view(view)
        assert {k for k,v in case.page_styles(view,case.page(view)).items() if v}==expected
    finally:case.close()


def test_graphical_layout_preserves_descending_icon_threshold_comparisons_and_floor(tmp_path):
    path=tmp_path/'s.layout'
    icons=''.join(f'<property name="Item{i}"><property name="Value">{v}</property><property name="ValueComparison">Greater</property></property>' for i,v in enumerate([67,33,0]))
    path.write_text(f'''<XtraSerializer><property name="Columns"><property name="Item1"><property name="FieldName">Value</property></property></property><property name="FormatRules"><property name="Item1"><property name="ColumnName">Value</property><property name="RuleType">#FormatConditionRuleIconSet</property><property name="Rule"><property name="IconSet"><property name="ValueType">Number</property><property name="Icons">{icons}</property></property></property></property></property></XtraSerializer>''')
    rule=read_tle_layout(path,['Value']).view.format_rules[0]
    assert rule.icon_thresholds==['33','67'] and rule.icon_comparisons==['>','>'] and rule.icon_floor=='0' and rule.icon_floor_comparison=='>'
    from fireblade.ui.visual_rules import icon_level
    assert [icon_level(rule,str(v),max(0,min(1,v/100))) for v in [-1,0,1,33,34,67,68]]==[-1,-1,0,0,1,1,2]


@pytest.mark.parametrize('kind,properties,expected',[
 ('UniqueDuplicate','<property name="FormatType">Unique</property>',{3}),
 ('AboveBelowAverage','<property name="AverageType">EqualOrAbove</property>',{3}),
 ('Contains','<property name="Values"><property name="Item1">1</property><property name="Item2">3</property></property>',{1,2,3}),
 ('Value','<property name="Condition">None</property>',{1,2,3}),
])
def test_documented_xml_variants_and_predefined_style(tmp_path,kind,properties,expected):
    path=tmp_path/'s.layout';path.write_text(f'''<XtraSerializer><property name="Columns"><property name="Item1"><property name="FieldName">Value</property></property></property><property name="FormatRules"><property name="Item1"><property name="ColumnName">Value</property><property name="RuleType">#FormatConditionRule{kind}</property><property name="Rule">{properties}<property name="PredefinedName">Red Bold Text</property></property></property></property></XtraSerializer>''')
    source=tmp_path/'s.csv';source.write_text('Value\n1\n1\n3\n');case=Case(tmp_path/'s.timeline')
    try:
        case.import_csv(source);view=read_tle_layout(path,case.headers).view;case.validate_view(view)
        assert view.format_rules[0].bold and view.format_rules[0].use_foreground and not view.format_rules[0].use_background
        assert {k for k,v in case.page_styles(view,case.page(view)).items() if v}==expected
    finally:case.close()
