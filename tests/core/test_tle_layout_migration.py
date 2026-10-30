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
    <property name="FormatRules"><property name="Item1"><property name="ApplyToRow">true</property><property name="RuleType">#FormatConditionRuleExpression</property><property name="Rule"><property name="Expression">[Size]&gt;5</property><property name="Appearance"><property name="BackColor">255, 0, 0</property><property name="ForeColor">White</property><property name="Font">Segoe UI, 10pt, style=Bold</property></property></property></property></property>
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
    finally:case.close()


def test_untranslatable_expression_or_format_rule_is_never_silently_dropped(tmp_path):
    path=tmp_path/'test.layout'
    prefix='<XtraSerializer><property name="Columns"><property name="Item1"><property name="FieldName">ID</property></property></property>'
    for value in ('<property name="ActiveFilterString">Unknown([ID])</property>', '<property name="FormatRules"><property name="Item1"><property name="RuleType">#UnknownRule</property></property></property>'):
        path.write_text(prefix+value+'</XtraSerializer>')
        with pytest.raises(ValueError):read_tle_layout(path,['ID'])
