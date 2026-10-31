from dataclasses import replace
from decimal import Decimal
import pytest
from fireblade.core.engine import Case
from fireblade.core.models import View,FormatRule,Filter
from fireblade.core.visual_bounds import resolve_rules


@pytest.mark.parametrize('mode,low,high,expected',[
 ('auto','0','100',('0E-10','100.0000000000')),
 ('percent','25','75',('25.0000000000','75.0000000000')),
 ('percentile','25','75',('7.500000000000','40.000000000000'))])
def test_bounds_cover_filtered_dataset_and_cache_not_visible_page(tmp_path,mode,low,high,expected):
    source=tmp_path/'s.csv';source.write_text('Value\n0\n10\n20\n100\n')
    case=Case(tmp_path/'s.timeline')
    try:
        case.import_csv(source)
        rule=FormatRule(target=0,visual='bar',bound_mode=mode,minimum=low,maximum=high)
        resolved=resolve_rules(case,View(),[rule])[0]
        assert (Decimal(resolved.minimum),Decimal(resolved.maximum))==tuple(map(Decimal,expected))
        assert rule.bound_mode==mode
        filtered=resolve_rules(case,View(filters=[Filter(0,'ge','10')]),[replace(rule,bound_mode='auto')])[0]
        assert Decimal(filtered.minimum)==10
        case.db.execute('DROP TABLE events')
        assert resolve_rules(case,View(),[rule])[0]==resolved
        assert not case.db.execute("SELECT table_name FROM information_schema.tables WHERE table_name LIKE '__fb_percentile_%'").fetchall()
    finally:case.close()


def test_middle_percentiles_zero_based_and_independent_percent_range(tmp_path):
    source=tmp_path/'s.csv';source.write_text('Value\n10\n20\n40\n100\n')
    case=Case(tmp_path/'s.timeline')
    try:
        case.import_csv(source)
        rule=FormatRule(target=0,visual='scale3',bound_mode='fixed',minimum='-100',maximum='200',middle_mode='percent',middle_value='50')
        resolved=resolve_rules(case,View(),[rule])[0]
        assert Decimal(resolved.middle_value)==55  # dataset 10..100, not fixed -100..200
        resolved=resolve_rules(case,View(),[replace(rule,middle_mode='percentile')])[0]
        assert Decimal(resolved.middle_value)==30
        resolved=resolve_rules(case,View(),[replace(rule,bound_mode='auto',zero_based=True)])[0]
        assert (Decimal(resolved.minimum),Decimal(resolved.maximum))==(0,100)
    finally:case.close()
