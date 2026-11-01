import copy
import xml.etree.ElementTree as ET

import pytest

from fireblade.core.engine import Case
from fireblade.core.models import Filter, FilterGroup, FormatRule, GroupSort, SortKey, Summary, View
from fireblade.core.tle_layout import read_tle_layout
from fireblade.core.tle_layout_export import build_tle_layout, write_tle_layout


HEADERS = ['User', 'Value', 'Time']
COLUMNS = [dict(column=0, position=1, width=190), dict(column=1, position=-1, width=80), dict(column=2, position=0, width=210)]


def test_xml_export_restores_columns_groups_footers_styles_and_rules(tmp_path):
    view = View(search='alice', groups=[0], group_order='summary', group_descending=False,
                group_sorts=[GroupSort(0, 'summary', 0, False)], summaries=[Summary(1, 'sum', 'number', 2)],
                total_summaries=[Summary(1, 'avg')], group_footer_mode='always',
                auto_row_height=True, row_height=28, group_row_height=39, header_height=51,
                pinned_columns=[2], right_pinned_columns=[0], timestamp_columns=[2],
                sorts=[SortKey(2, 'timestamp', True)], global_rules_enabled=False)
    view.layout_styles = {'row': {'background': '#80102030', 'word_wrap': True, 'high_priority': True},
                          'header:0': {'foreground': '#112233', 'font_family': 'Consolas', 'font_size': 12.5, 'bold': True}}
    view.format_rules = [FormatRule(FilterGroup('and', [Filter(0, 'eq', "O'Brien")]), background='#aabbcc', target=0)]
    target = tmp_path/'example.layout'
    warnings = write_tle_layout(target, HEADERS, view, COLUMNS)
    restored = read_tle_layout(target, HEADERS)
    assert restored.view.search == view.search
    assert restored.view.groups == [0] and restored.view.group_order == 'summary'
    assert restored.view.group_sorts[0] == view.group_sorts[0]
    assert restored.view.summaries == view.summaries
    assert restored.view.total_summaries == view.total_summaries
    assert restored.view.group_footer_mode == 'always'
    assert restored.view.pinned_columns == [2] and restored.view.right_pinned_columns == [0]
    assert restored.view.auto_row_height and restored.view.row_height == 28
    assert restored.view.group_row_height == 39 and restored.view.header_height == 51
    assert restored.view.layout_styles['row'] == view.layout_styles['row']
    for key, value in view.layout_styles['header:0'].items():
        assert restored.view.layout_styles['header:0'][key] == value
    assert restored.columns[1]['position'] == -1
    assert restored.view.format_rules[0].background == '#aabbcc'
    assert restored.view.format_rules[0].target == 0
    assert any('qualifier' in warning for warning in warnings)
    assert any('Polices partielles' in warning for warning in warnings)
    assert any('type numérique' in warning for warning in warnings)
    assert ET.parse(target).getroot().tag == 'XtraSerializer'


@pytest.mark.parametrize('condition', [
    Filter(0, 'ne', 'alice'), Filter(0, 'contains', 'AL'), Filter(0, 'not_contains', 'al'),
    Filter(0, 'empty'), Filter(0, 'not_empty'), Filter(0, 'starts', 'a'), Filter(0, 'ends', 'e'),
    Filter(1, 'ge', '2'), Filter(2, 'after', '2026-01-02'),
    FilterGroup('or', [Filter(0, 'eq', "O'Brien"), Filter(1, 'lt', '2')]),
    FilterGroup('not', [Filter(0, 'eq', 'alice')]),
])
def test_exported_criteria_select_same_source_events(tmp_path, condition):
    source = tmp_path/'data.csv'
    source.write_text("User,Value,Time\nalice,1,2026-01-01\nBOB,2,2026-01-02\nO'Brien,3,2026-01-03\n,4,2026-01-04\n")
    case = Case(tmp_path/'data.timeline')
    try:
        case.import_csv(source)
        before = View(expression=FilterGroup('and', [condition]), global_rules_enabled=False)
        target = tmp_path/'data.layout'
        write_tle_layout(target, HEADERS, before, COLUMNS)
        after = read_tle_layout(target, HEADERS).view
        assert case.count(before) == case.count(after)
    finally:
        case.close()


@pytest.mark.parametrize('visual', ['bar', 'scale', 'scale3', 'icon'])
def test_exported_graphical_bounds_units_and_priority_survive(tmp_path, visual):
    rule = FormatRule(visual=visual, target=1, value_column=1, minimum='-10', maximum='90',
                      bound_mode='fixed', maximum_mode='percentile', middle_mode='percentile', middle_value='45',
                      icon_thresholds=['50', '3'], icon_threshold_modes=['percentile', 'number'],
                      icon_floor='10', icon_floor_mode='percent', icon_comparisons=['>', '>='],
                      use_font=False, stop_if_true=False)
    view = View(format_rules=[rule], global_rules_enabled=False)
    target = tmp_path/'graphic.layout'
    write_tle_layout(target, HEADERS, view, COLUMNS)
    result = read_tle_layout(target, HEADERS).view.format_rules[0]
    assert result.visual == visual and result.target == 1 and result.value_column == 1
    assert result.minimum == '-10' and result.maximum == '90'
    assert result.maximum_mode == 'percentile'
    if visual == 'icon':
        assert result.icon_thresholds == ['50', '3']
        assert result.icon_threshold_modes == ['percentile', 'number']
        assert result.icon_comparisons == ['>', '>=']
        assert result.icon_floor == '10' and result.icon_floor_mode == 'percent'


@pytest.mark.parametrize('statistic', ['top', 'bottom', 'above_avg', 'below_avg', 'above_eq_avg', 'below_eq_avg', 'unique', 'duplicate'])
def test_statistical_export_keeps_operation_and_target(tmp_path, statistic):
    rule = FormatRule(statistic=statistic, value_column=1, target=None, bold=True, stat_rank='25', stat_percent=True)
    target = tmp_path/'statistic.layout'
    write_tle_layout(target, HEADERS, View(format_rules=[rule]), COLUMNS)
    result = read_tle_layout(target, HEADERS).view.format_rules[0]
    assert result.statistic == statistic and result.value_column == 1
    assert result.target is None and result.bold
    if statistic in ('top', 'bottom'):
        assert result.stat_rank == '25' and result.stat_percent


def test_unrepresentable_rule_or_broken_write_keeps_destination(tmp_path, monkeypatch):
    target = tmp_path/'keep.layout'
    target.write_text('existing')
    rule = FormatRule(visual='bar', target=1, all_source_rows=True)
    with pytest.raises(ValueError, match='Population'):
        write_tle_layout(target, HEADERS, View(format_rules=[rule]), COLUMNS)
    assert target.read_text() == 'existing'
    import fireblade.core.tle_layout_export as module
    def fail(*args):
        raise OSError('replace failed')
    monkeypatch.setattr(module.os, 'replace', fail)
    with pytest.raises(OSError):
        write_tle_layout(target, HEADERS, View(), COLUMNS)
    assert target.read_text() == 'existing'
    assert list(tmp_path.iterdir()) == [target]


def test_original_tle_control_names_and_bound_fields_survive_a_source_alias(tmp_path):
    headers=['Raw Header','Other']
    view=View(tle_fields={'0':dict(name='colTypedValue',field='TypedValue')},
              expression=FilterGroup('and',[Filter(0,'expression',"[Raw Header] = 'Raw Header' And [Other] <> 'x'")]))
    columns=[dict(column=0,position=0,width=150),dict(column=1,position=1,width=150)]
    payload=build_tle_layout(headers,view,columns)
    xml=ET.fromstring(payload.data)
    columns_node=xml.find("property[@name='Columns']")
    first=columns_node[0]
    assert first.find("property[@name='Name']").text=='colTypedValue'
    assert first.find("property[@name='FieldName']").text=='TypedValue'
    expression=xml.find("property[@name='ActiveFilterString']").text
    assert "[TypedValue] = 'Raw Header'" in expression
    assert "[Other] <> 'x'" in expression


def test_imported_binding_metadata_is_persisted_with_the_view(tmp_path):
    source=tmp_path/'binding.layout'
    source.write_text('<XtraSerializer><property name="Columns"><property name="Item1"><property name="Name">colUser</property><property name="FieldName">User</property></property></property></XtraSerializer>')
    view=read_tle_layout(source,['User']).view
    assert View.from_json(view.to_json()).tle_fields=={'0':dict(name='colUser',field='User')}


def test_original_collection_criteria_are_reexported_until_the_filter_changes(tmp_path):
    source=tmp_path/'collection.layout'
    expression="[Details.Children].Sum([Amount]) > 5"
    source.write_text('<XtraSerializer><property name="Columns"><property name="Item1"><property name="Name">colDetails</property></property></property><property name="ActiveFilterString">'+expression.replace('>','&gt;')+'</property></XtraSerializer>')
    view=read_tle_layout(source,['Details']).view
    assert view.tle_expressions
    columns=[dict(column=0,position=0,width=150)]
    result=build_tle_layout(['Details'],view,columns)
    xml=ET.fromstring(result.data)
    assert expression in xml.find("property[@name='ActiveFilterString']").text
    # A changed Fireblade helper must never reuse an obsolete original filter.
    view.expression.children[0].value='JsonSumExpr([Details], \'[Amount]\') > 99'
    with pytest.raises(ValueError,match='Expression Fireblade'):
        build_tle_layout(['Details'],view,columns)
