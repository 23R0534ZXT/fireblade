import csv
import pytest
from fireblade.core.engine import Case
from fireblade.core.filter_text import parse_filter
from fireblade.core.models import View,FilterGroup,Filter,FormatRule
from fireblade.core.rule_store import RuleBook


@pytest.fixture
def case(tmp_path):
    source=tmp_path/'expressions.csv'
    with source.open('w',encoding='utf-8',newline='') as f:
        csv.writer(f).writerows([['Name','N','Other','Date'],[' Alice ','9007199254740993','1','2026-10-30 12:34:56.1234567'],['BOB','10','2','2025-01-02 01:02:03'],['Carol','2','3','invalid'],['','','','']])
    c=Case(tmp_path/'e.timeline');c.import_csv(source)
    yield c
    c.close()


@pytest.mark.parametrize(('expression','expected'),[
    ("Upper(Trim([Name])) = 'ALICE'",[1]),
    ("Len([Name]) = 3",[2]),
    ("Substring([Name], 1, 3) = 'Ali'",[1]),
    ("Replace([Name], 'B', 'b') = 'bOb'",[2]),
    ("Contains(Lower([Name]), 'car')",[3]),
    ("ToInt([N]) > 9007199254740992",[1]),
    ("[N] * 2 = 20",[2]),
    ("[N] + [Other] = 5",[3]),
    ("ToInt('10') = [N]",[2]),
    ("Iif([N] > 100, 'large', 'small') = 'large'",[1]),
    ("IsNull([Name], 'empty') = 'empty'",[4]),
    ("Concat(Trim([Name]), '!') = 'Alice!'",[1]),
    ("PadLeft(ToStr(ToInt([N])), 3, '0') = '002'",[3]),
    ("CharIndex('o', Lower([Name])) >= 1",[2,3]),
    ("[Name] Like '%o%'",[2,3]),
    ("[Name] Not Like '%o%'",[1,4]),
    ("[N] Is Null",[4]),
    ("[N] Is Not Null And [Other] >= 2",[2,3]),
    ("GetYear([Date]) = 2026",[1]),
    ("GetMonth([Date]) = 1 And GetDay([Date]) = 2",[2]),
    ("GetHour([Date]) = 12 And GetMinute([Date]) = 34",[1]),
    ("DateDiffDay(#2025-01-01#, [Date]) = 1",[2]),
    ("GetDay(AddDays([Date], 1)) = 3",[2]),
    ("Round([Other] / 2, 1) = 1.5",[3]),
    ("Abs(-[Other]) = 2",[2]),
    ("RegexIsMatch([Name], '^B.*')",[2]),
])
def test_advanced_expressions_execute_as_bound_queries(case,expression,expected):
    view=View(expression=parse_filter(expression,case.headers))
    assert [r[0] for r in case.page(view)]==expected
    assert View.from_json(view.to_json())==view


@pytest.mark.parametrize('text',["ReadCsv('secret') = 1","[N] = 1; DROP TABLE events","Contains([Name], 'x') OR __import__('os')", "Unknown([N])",'(' * 40 + '[N] = 1' + ')' * 40])
def test_unknown_code_or_excess_depth_is_rejected(case,text):
    with pytest.raises(ValueError):parse_filter(text,case.headers)
    assert case.count(View())==4


def test_named_expression_global_rules_follow_schema_and_are_page_local(case):
    rule=FormatRule(FilterGroup('and',[Filter(0,'expression',"Upper(Trim([Name])) = 'ALICE' And [N] > 100")]))
    book=RuleBook(case.headers,[rule]);encoded=book.to_bytes();assert RuleBook.from_bytes(encoded)==book
    rules,skipped=book.adapt(case.headers);assert not skipped
    assert case.page_styles(View(),case.page(View()),rules)=={1:(0,),2:(),3:(),4:()}
    reordered=['Date','Other','N','Name'];rules,skipped=book.adapt(reordered);assert not skipped
    from fireblade.core.expressions import compile_expression
    sql,params=compile_expression(rules[0].condition.children[0].value,reordered,lambda i:f'"c{i}"',lambda c:f'try_cast({c} AS DECIMAL(38,10))')
    assert '"c3"' in sql and 'ALICE' not in sql and 'ALICE' in params
    assert book.adapt(['Other'])[1]


def test_virtual_line_tag_and_note_work_in_filters_and_shared_rules(case):
    case.bookmark(2,'priority')
    assert case.count(View(expression=parse_filter('[Tag] = True',case.headers)))==1
    assert case.count(View(expression=parse_filter('[Tag] = False',case.headers)))==3
    assert [r[0] for r in case.page(View(expression=parse_filter("[Line] >= 2 And Contains([Note], 'prio')",case.headers)))]==[2]
    rule=FormatRule(FilterGroup('and',[Filter(0,'expression','[Tag] = True')]))
    book=RuleBook(case.headers,[rule]);rules,skipped=book.adapt(case.headers)
    assert not skipped
    assert case.page_styles(View(),case.page(View()),rules)=={1:(),2:(0,),3:(),4:()}


@pytest.mark.parametrize('text',[
    "Insert('abc',1,'X')='aXbc'", "Remove('abc',1,1)='ac'", "Remove('abc',1)='a'",
    "PadLeft('abc',1)='abc'", "PadRight('a',3,'x')='axx'", "Char(65)='A'", "Ascii('A')=65", "Log(8,2)=3",
    "Concat('[N]','?')='[N]?'",
])
def test_additional_scalar_functions_preserve_values_and_parameter_order(case,text):
    assert case.count(View(expression=parse_filter(text,case.headers)))==4


def test_long_flat_logic_is_not_mistaken_for_nested_parentheses(case):
    text=' And '.join(["Abs([Other]) >= 0"]*50)
    assert case.count(View(expression=parse_filter(text,case.headers)))==3


def test_annotation_changes_invalidate_sorted_filter_cache(tmp_path):
    from fireblade.core.settings import Settings
    source=tmp_path/'cache.csv';source.write_text('ID\n'+'\n'.join(str(i) for i in range(1,61))+'\n')
    case=Case(tmp_path/'cache.timeline',settings=Settings(page_size=25,max_loaded_rows=25))
    try:
        case.import_csv(source);case.bookmark_many(range(1,41))
        view=View(expression=parse_filter('[Tag] = True',case.headers),sort_column=0,sort_type='number')
        assert [r[0] for r in case.page(view,offset=25)]==list(range(26,41))
        case.bookmark_many(range(1,31),mode='remove')
        assert case.page(view,offset=25)==[]
        assert [r[0] for r in case.page(view)]==list(range(31,41))
        case.add_derived_columns([dict(name='IsTagged',operation='expression',expression='Iif([Tag], 1, 0)')])
        assert case.page(View())[0][-1]=='0.0000000000'
        case.bookmark(1,'changed')
        assert case.page(View())[0][-1]=='1.0000000000'
    finally:case.close()


def test_nested_date_functions_and_comparisons_keep_submicrosecond_values(tmp_path):
    source=tmp_path/'ns.csv';source.write_text('Time\n2026-01-01T00:00:00.123456799Z\n2026-01-01T01:00:00.123456700+01:00\n2026-01-01T00:00:00.123456701Z\n')
    case=Case(tmp_path/'ns.timeline')
    try:
        case.import_csv(source)
        for text in ("Iif([Time] = #2026-01-01T00:00:00.123456701Z#,True,False)",
                     "ToDateTime([Time]) = #2026-01-01T00:00:00.123456701Z#",
                     "AddDays([Time],1) = #2026-01-02T00:00:00.123456701Z#",
                     "AddMonths([Time],1) = #2026-02-01T00:00:00.123456701Z#",
                     "AddYears([Time],1) = #2027-01-01T00:00:00.123456701Z#",
                     "AddMilliseconds([Time],0.000001) = #2026-01-01T00:00:00.123456702Z#",
                     "Iif(True,ToDateTime([Time]),#2000-01-01#) = #2026-01-01T00:00:00.123456701Z#",
                     "AddTicks([Time],1) = #2026-01-01T00:00:00.123456801Z#",
                     "AddMicroseconds([Time],1) = #2026-01-01T00:00:00.123457701Z#",
                     "DateDiffNanosecond(#2026-01-01T00:00:00.123456700Z#,[Time]) = 1",
                     "ToStr(ToDateTime([Time])) = '2026-01-01T00:00:00.123456701Z'"):


            assert [r[0] for r in case.page(View(expression=parse_filter(text,case.headers)))]==[3],text
        case.add_derived_columns([dict(name='Tomorrow',operation='expression',expression='AddDays([Time],1)')])
        assert case.page(View())[0][-1]=='2026-01-02T00:00:00.123456799Z'
    finally:case.close()
