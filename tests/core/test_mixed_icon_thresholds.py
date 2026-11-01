from dataclasses import replace
from decimal import Decimal

import pytest

from fireblade.core.engine import Case
from fireblade.core.models import Filter, FormatRule, View
from fireblade.core.tle_layout import read_tle_layout
from fireblade.core.visual_bounds import resolve_rules
from fireblade.ui.visual_rules import icon_level


def mixed_layout(path):
    # DevExpress stores highest-priority icon first. Raw 50 percentile must
    # remain above the 200 fixed threshold, not be sorted below it as a number.
    entries=''.join(f'<property name="Item{i}"><property name="Value">{value}</property><property name="ValueType">{mode}</property><property name="ValueComparison">{comparison}</property></property>'
                    for i,(value,mode,comparison) in enumerate([('50','Percentile','Greater'),('200','Number','GreaterOrEqual'),('0','Percent','GreaterOrEqual')]))
    path.write_text(f'<XtraSerializer><property name="Columns"><property name="Item1"><property name="FieldName">Value</property></property></property><property name="FormatRules"><property name="Item1"><property name="ColumnName">Value</property><property name="RuleType">#FormatConditionRuleIconSet</property><property name="Rule"><property name="IconSet"><property name="ValueType">Number</property><property name="Icons">{entries}</property></property></property></property></property></XtraSerializer>')
    return read_tle_layout(path,['Value']).view


def test_xml_mixed_units_filter_cache_and_rendered_levels(tmp_path):
    view=mixed_layout(tmp_path/'mixed.layout')
    rule=view.format_rules[0]
    assert rule.icon_thresholds==['200','50']
    assert rule.icon_threshold_modes==['number','percentile']
    assert rule.icon_floor_mode=='percent'  # per-entry override, not set default
    assert View.from_json(view.to_json()).format_rules[0]==rule
    source=tmp_path/'s.csv';source.write_text('Value\n0\n100\n200\n1000\n')
    with_case=Case(tmp_path/'s.timeline')
    try:
        with_case.import_csv(source);with_case.validate_view(view)
        resolved=resolve_rules(with_case,view,[rule])[0]
        assert list(map(Decimal,resolved.icon_thresholds))==[200,150]
        # The percentile threshold crosses the fixed one: high priority still
        # wins. Counting matching thresholds would choose the wrong icon.
        assert [icon_level(resolved,value,0) for value in ['0','150','151','200','1000']]==[0,0,2,2,2]
        filtered=replace(view,filters=[Filter(0,'ge','100')])
        second=resolve_rules(with_case,filtered,[rule])[0]
        assert list(map(Decimal,second.icon_thresholds))==[200,200]
        assert [icon_level(second,value,0) for value in ['99','100','200','201']]==[-1,0,1,2]
        assert resolve_rules(with_case,view,[rule])[0]==resolved
        assert not with_case.db.execute("SELECT table_name FROM information_schema.tables WHERE table_name LIKE '__fb_percentile_%'").fetchall()
    finally:with_case.close()


def test_mixed_units_have_independent_validation_and_cache_keys(tmp_path):
    source=tmp_path/'s.csv';source.write_text('Value\n0\n10\n20\n100\n')
    case=Case(tmp_path/'s.timeline')
    try:
        case.import_csv(source)
        rule=FormatRule(target=0,visual='icon',bound_mode='auto',icon_thresholds=['25','75'],icon_threshold_modes=['percent','percentile'])
        case.validate_view(View(format_rules=[rule]))
        a=resolve_rules(case,View(),[rule])[0]
        b=resolve_rules(case,View(),[replace(rule,icon_threshold_modes=['percentile','percent'])])[0]
        assert list(map(Decimal,a.icon_thresholds))==[25,40]
        assert list(map(Decimal,b.icon_thresholds))==[Decimal('7.5'),75]
        for invalid in (['number'],['number','bogus'],['percent','percentile','number']):
            with pytest.raises(ValueError):case.validate_view(View(format_rules=[replace(rule,icon_threshold_modes=invalid)]))
        with pytest.raises(ValueError):case.validate_view(View(format_rules=[replace(rule,icon_thresholds=['200','75'])]))
    finally:case.close()
