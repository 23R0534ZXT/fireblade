from dataclasses import replace
import pytest
from fireblade.core.engine import Case
from fireblade.core.models import View,FormatRule,Filter


@pytest.mark.parametrize('mode,expected', [('top',{5}),('bottom',{1,2}),('above_avg',{5}),('below_avg',{1,2,3,4}),('unique',{3,4,5}),('duplicate',{1,2})])
def test_statistics_use_full_filtered_data_and_include_ties(tmp_path,mode,expected):
    source=tmp_path/'s.csv';source.write_text('Value\n1\n1\n3\n5\n100\n')
    case=Case(tmp_path/'s.timeline')
    try:
        case.import_csv(source);rule=FormatRule(target=0,statistic=mode,stat_rank='1')
        view=View(format_rules=[rule]);case.validate_view(view)
        rows=case.page(view)
        assert {k for k,v in case.page_styles(view,rows).items() if v}==expected
        # Only rendering the first page must not change the statistical population.
        assert {k for k,v in case.page_styles(view,rows[:2]).items() if v}==expected.intersection({1,2})
        if mode=='top':
            filtered=replace(view,filters=[Filter(0,'le','5')])
            assert {k for k,v in case.page_styles(filtered,case.page(filtered)).items() if v}=={4}
    finally:case.close()


def test_duplicates_case_null_and_collision_candidates_are_verified(tmp_path):
    source=tmp_path/'s.csv';source.write_text('Value\nAlice\nalice\nBob\n""\n""\n')
    case=Case(tmp_path/'s.timeline')
    try:
        case.import_csv(source);rule=FormatRule(target=0,statistic='duplicate',stat_ignore_case=True,stat_include_null=True)
        view=View(format_rules=[rule]);rows=case.page(view)
        assert {k for k,v in case.page_styles(view,rows).items() if v}=={1,2,4,5}
        # Simulate a hash collision for a unique value: verify original strings.
        table=next(iter(case._stat_frequencies.values()));case.db.execute(f'UPDATE "{table}" SET n=100')
        case._stat_counts.clear();case._stat_bytes=0
        assert case.page_styles(view,rows)[3]==()
    finally:case.close()


def test_inclusive_average_and_explicit_all_source_scope(tmp_path):
    source=tmp_path/'s.csv';source.write_text('Value\n1\n2\n3\n')
    case=Case(tmp_path/'s.timeline')
    try:
        case.import_csv(source)
        for mode,expected in [('above_eq_avg',{2,3}),('below_eq_avg',{1,2})]:
            view=View(format_rules=[FormatRule(target=0,statistic=mode)])
            assert {k for k,v in case.page_styles(view,case.page(view)).items() if v}==expected
        view=View(filters=[Filter(0,'le','2')],format_rules=[FormatRule(target=0,statistic='top',stat_rank='1',all_source_rows=True)])
        assert not any(case.page_styles(view,case.page(view)).values())
        view.format_rules[0].all_source_rows=False
        assert {k for k,v in case.page_styles(view,case.page(view)).items() if v}=={2}
    finally:case.close()
