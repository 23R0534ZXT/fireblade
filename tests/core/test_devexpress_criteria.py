import csv
import datetime
from decimal import Decimal
import json
import uuid
import pytest
from fireblade.core.engine import Case
from fireblade.core.models import View,FormatRule,Filter,FilterGroup
from fireblade.core.filter_text import parse_filter


@pytest.fixture
def case(tmp_path):
    source=tmp_path/'criteria.csv'
    data=[{'Amount':3,'Limit':5,'Name':'a','Sub':[{'Cost':2},{'Cost':9}]},{'Amount':12,'Limit':8,'Name':'b','Sub':[{'Cost':11}]}]
    with source.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.writer(stream);writer.writerow(['Name','Value','Limit','Date','ID','Or','Items'])
        writer.writerow(['alice',12,10,'2026-01-02 12:34:56.1234567','513724E5-17B7-4EC6-ABC4-0EAE12C72C1F','yes',json.dumps(data)])
        writer.writerow(['bob',3,20,'2025-03-01 00:00:00','00000000-0000-0000-0000-000000000000','no','[]'])
    result=Case(tmp_path/'criteria.timeline');result.import_csv(source)
    yield result
    result.close()


@pytest.mark.parametrize('expression',[
 "Value = 12m And Name = 'alice'", "@Or = 'yes'", "[Value] = 12s", "[Value] = 12b", "12.0f=12.0m", "12L=12UL", "'a'c='a'",
 "ID = {513724e5-17b7-4ec6-abc4-0eae12c72c1f}",
 "[Date] >= #!2026-01-01!#", "#!12:34:56.1234567!# > #!12:34:56.1234566!#",
 "InRange(Value,10,13)","Not InRange(Value,0,12)","CharIndex('a','banana',2)=3", "CharIndex('x','banana',2)=-1",
 "Abs(Atn(1)-Atan(1))<0.00001", "Atn2(1,1)=Atan2(1,1)","Sqr(9)=3", "Cosh(0)=1", "Sinh(0)=0", "Tanh(0)=0", "Truncate(-3.9)=-3", "Pi()>3", "Rnd()>=0 And Rnd()<1",
 "IsJanuary([Date])", "IsSameDay([Date],#2026-01-02 01:00:00#)", "IsSameHour([Date],#2026-01-02 12:00:00#)",
 "DateTimeFromParts(2026,1,2,12,34,56,123)=#2026-01-02 12:34:56.123#", "DateOnlyFromParts(2026,1,2)=GetDate([Date])",
 "GetHour(TimeOnlyFromParts(12,34,56,123))=12", "TimeOnlyFromParts(24,0) Is Null",
 "GetTimeOfDay([Date])=452961234567", "AddTimeSpan(#2026-01-01#,10)=#2026-01-01 00:00:00.0000010#",
 "InDateRange([Date],#2026-01-02 19:00:00#,#2026-01-02 20:00:00#)", "IsAfternoon(#!12:34!#)",
 "GetHour(AddHours(#!23:00!#,2))=1", "IsNullOrWhiteSpace('  ')",
 '[Items][[Amount]>10]', '[Items][]', 'Items[Amount>10].Exists()', '[Items][[Amount]>[^.Limit]].Count()=1',
 '[Items][[Amount]>[^.Limit]].Sum([Amount])=12',
 '[Items].Sum([Sub][[Cost]>[^.Limit]].Sum([Cost]))=20',
 '[Items].Sum([Sub][[Cost]>[^.^.Limit]].Sum([Cost]))=11',
 '[Items][[Sub][[Cost]>[^.Limit]]].Count()=2',
 '[Items].Sum([Sub].Sum([Cost]+[^.Amount]))=40',
])
def test_devexpress_advanced_criteria_execute_as_native_queries(case,expression):
    view=View(expression=parse_filter('('+expression+") And Name='alice'",case.headers))
    assert [row[0] for row in case.page(view)]==[1],expression
    assert View.from_json(view.to_json())==view


def test_positional_parameters_are_escaped_typed_and_persisted(case):
    view=View(expression=parse_filter('Name=? And Value>?',case.headers,['alice',Decimal('10')]))
    assert case.count(view)==1
    assert View.from_json(view.to_json())==view
    assert case.count(View(expression=parse_filter('Name=?',case.headers,["alice' Or True Or Name='bob"])))==0
    assert case.count(View(expression=parse_filter('[Date]>=?',case.headers,[datetime.datetime(2026,1,1)])))==1
    assert case.count(View(expression=parse_filter('ID=?',case.headers,[uuid.UUID('513724e5-17b7-4ec6-abc4-0eae12c72c1f')])))==1
    assert case.count(View(expression=parse_filter('[Items][[Amount]>?]',case.headers,[10])))==1
    assert case.count(View(expression=parse_filter('Contains(\'?\',\'?\') And Name=?',case.headers,['alice'])))==1


@pytest.mark.parametrize('expression',["'ab'c='a'",'256b=256','32768s=32768','-1UL=1','ID > {513724e5-17b7-4ec6-abc4-0eae12c72c1f}','[Items][[Amount]>[^.^.Limit]]','[Missing][]'])
def test_invalid_typed_constants_and_parent_scopes_are_rejected(case,expression):
    with pytest.raises(ValueError):parse_filter(expression,case.headers)


def test_advanced_criteria_shared_by_coloring_derived_columns_and_export(case,tmp_path):
    expression='[Items][[Amount]>[^.Limit]].Exists() And InRange(Value,10m,20m)'
    rules=[FormatRule(FilterGroup('and',[Filter(0,'expression',expression)]),background='#ff0000')]
    rows=case.page(View())
    assert {row_id for row_id,matched in case.page_styles(View(),rows,rules).items() if matched}=={1}
    case.add_derived_columns([dict(name='SelectedTotal',operation='expression',expression='[Items][[Amount]>[^.Limit]].Sum([Amount])')])
    assert Decimal(case.page(View())[0][-1])==12
    target=tmp_path/'filtered.csv';case.export(target,View(expression=parse_filter(expression,case.headers)))
    with target.open(encoding='utf-8-sig',newline='') as stream:assert [row[0] for row in list(csv.reader(stream))[1:]]==['alice']


def test_layout_aliases_respect_collection_scopes_and_parent_references(case,tmp_path):
    from fireblade.core.tle_layout import read_tle_layout
    xml=tmp_path/'advanced.layout'
    columns=''.join(f'<property name="Item{i}"><property name="Name">col{field}</property><property name="FieldName">{field}</property></property>' for i,field in enumerate(case.headers))
    xml.write_text(f'''<XtraSerializer><property name="Columns">{columns}</property><property name="ActiveFilterString">[colItems][[Amount]&gt;[^.colLimit]].Count()=1 And colName='alice'</property></XtraSerializer>''')
    layout=read_tle_layout(xml,case.headers)
    assert case.count(layout.view)==1
    xml.write_text(f'''<XtraSerializer><property name="Columns">{columns}</property><property name="ActiveFilterString">[colItems].Sum([Sub][[Cost]&gt;[^.^.colLimit]].Sum([Cost]))=11</property></XtraSerializer>''')
    assert case.count(read_tle_layout(xml,case.headers).view)==1


def test_parent_dependencies_survive_shared_rule_mapping_and_parameter_defaults(case):
    from fireblade.core.rule_store import RuleBook
    expression='[Items][[Amount]>[^.Limit]].Exists()'
    book=RuleBook(case.headers,[FormatRule(FilterGroup('and',[Filter(0,'expression',expression)]))])
    restored=RuleBook.from_bytes(book.to_bytes())
    assert restored.adapt(list(reversed(case.headers)))[0]
    assert restored.adapt([h for h in case.headers if h!='Limit'])[1]
    assert case.count(View(expression=parse_filter('Name=?',case.headers)))==0
    assert case.count(View(expression=parse_filter('Value>?',case.headers)))==0


def test_submicrosecond_tick_boundaries_and_float_suffixes(case):
    expression="DateDiffTick(#1969-12-31 23:59:59.999999999#,#1970-01-01#)=1 And 1e30d>1e29d And 1e20f>1e19f"
    assert case.count(View(expression=parse_filter(expression,case.headers)))==2


@pytest.mark.parametrize('expression',[
 "AddTimeSpan(#2026-01-01#,'01:02:03.0000001')=#2026-01-01 01:02:03.0000001#",
 "AddTimeSpan(#2026-01-02#,'-1.00:00:00')=#2026-01-01#",
 "AddTimeSpan(#2026-01-01#,'bad') Is Null",
 "AddTimeSpan(#2026-01-01#,'00:99:00') Is Null",
])
def test_timespan_strings_preserve_tick_precision(case,expression):
    assert case.count(View(expression=parse_filter(expression,case.headers)))==2
