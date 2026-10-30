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
