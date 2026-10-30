import base64
import csv
import json
from pathlib import Path
from decimal import Decimal

import pytest

from fireblade.core.engine import Case
from fireblade.core.filter_text import parse_filter
from fireblade.core.models import Filter, Summary, View
from fireblade.core.profile_plugins import load_plugins
from fireblade.core.profiles import detect_profile, profile_view
from fireblade.core.timestamps import display_timestamp


@pytest.fixture
def case(tmp_path):
    source = tmp_path / 'records.csv'
    with source.open('w', encoding='utf-8', newline='') as out:
        writer = csv.writer(out)
        writer.writerows([
            ['Date','Type','ID','Flag','Description'],
            ['2026-01-01 01:00:00.1234567', 'A', '9007199254740993', 'TRUE', 'one'],
            ['2026-01-02 02:00:00', 'A', '1', 'FALSE', 'two'],
            ['2026-02-01 03:00:00', 'B', '5', 'TRUE', 'three'],
            ['invalid','B','invalid', '', ''],
            ['', 'B', '', '', "O'Brien"],
        ])
    case = Case(tmp_path / 'case.timeline')
    case.import_csv(source)
    yield case
    case.close()


def test_group_summaries_match_independent_values_and_respect_filters(case, tmp_path):
    view = View(groups=[1], summaries=[Summary(2,'sum'), Summary(2,'min'), Summary(2,'distinct')], group_order='summary', group_summary=0)
    rows = case.page(view)
    assert rows[0] == ('A', 2, Decimal('9007199254740994'), Decimal('1'), 2)
    assert rows[1] == ('B', 3, Decimal('5'), Decimal('5'), 2)
    assert case.page(View(groups=[1], group_order='value', group_descending=False))[0][0] == 'A'
    view.filters = [Filter(2, 'gt', '3')]
    assert [r[:2] for r in case.page(view)] == [('A',1),('B',1)]
    target = tmp_path / 'summaries.csv'
    case.export(target, view, grouped=True)
    with target.open(encoding='utf-8-sig', newline='') as incoming:
        exported = list(csv.reader(incoming))
    assert exported[0] == ['Type','Count','sum(ID)','min(ID)','distinct(ID)']
    assert exported[1][0] == 'A'


def test_temporal_groups_use_same_expression_for_child_navigation_and_export(case, tmp_path):
    view = View(groups=[0,1], group_intervals={'0':'month'}, group_order='value', group_descending=False)
    assert case.page(view) == [('2026-01',2),('2026-02',1),(None,2)]
    assert case.page(view, ('2026-01',)) == [('A',2)]
    assert [r[0] for r in case.page(view, ('2026-01','A'))] == [1,2]
    view.summaries = [Summary(2,'max')]
    target = tmp_path / 'dates.csv'
    case.export(target, view, grouped=True)
    assert '2026-01,A,2,9007199254740993' in target.read_text(encoding='utf-8-sig')


def test_export_visible_columns_is_projection_not_page_or_display_truncation(case, tmp_path):
    target = tmp_path / 'view.csv'
    case.export(target, View(filters=[Filter(1,'eq','A')], sort_column=2, sort_type='number'), columns=[4,2])
    with target.open(encoding='utf-8-sig', newline='') as incoming:
        assert list(csv.reader(incoming)) == [['Description','ID'],['two','1'],['one','9007199254740993']]
    with pytest.raises(ValueError):
        case.export(target, View(), columns=[])
    with pytest.raises(ValueError):
        case.export(target, View(), columns=[999])


@pytest.mark.parametrize(('text','count'), [
    ("Contains([Description], 'ONE') Or [ID] >= 5", 2),
    ("[Type] In ('A','B') And Not IsNullOrEmpty([ID])", 4),
    ("[ID] Between 1 And 5", 2),
    ("[Description] = 'O''Brien'", 1),
    ("[Date] >= #2026-01-01# And [Date] < #2026-02-01#", 2),
    ("[Flag] = True And EndsWith([Description], 'ree')", 1),
    ("Not (StartsWith([Description], 'o') Or [Type] <> 'B')", 2),
    ("[ID] Not In (1, 5)", 3),
])
def test_text_filter_parser_compiles_bound_conditions(case, text, count):
    view = View(expression=parse_filter(text, case.headers))
    assert case.count(view) == count


@pytest.mark.parametrize('text', ["[missing] = 1", "__import__('os')", "[ID] = 1; DROP TABLE events", "Contains([ID])", "Iif([ID],1)", "("*30 + "[ID]=1" + ")"*30])
def test_text_filter_rejects_unknown_or_executable_syntax(case, text):
    with pytest.raises(ValueError):
        parse_filter(text, case.headers)
    assert case.count(View()) == 5


def test_xls_selected_sheet_preserves_text_and_reads_cached_formula_values(tmp_path):
    fixture = json.loads((Path(__file__).parents[1]/'fixtures/legacy-workbook.json').read_text())
    source = tmp_path/'legacy.xls'
    source.write_bytes(base64.b64decode(fixture['base64']))
    from fireblade.core.legacy_excel import sheet_names
    assert sheet_names(source) == ['Premier','Preuves']
    case = Case(tmp_path/'legacy.timeline')
    try:
        case.import_excel(source, 'Preuves')
        assert case.info['format'] == 'xls'
        assert case.headers == ['ID','When','Flag','Text']
        rows = case.page(View())
        assert rows[0][1:] == ('0001',None,'TRUE','évidence')
        assert rows[1][1] == '9007199254740993'
        assert rows[1][-1] == '=literal'
    finally:
        case.close()


def test_custom_profile_loading_does_not_execute_code_and_reports_invalid_plugins(tmp_path):
    profile = dict(name='Custom evidence', signature=['Event','Time'], timestamp=['Time'], booleans=['Flag'], columns=['Time','Event'])
    (tmp_path/'good.json').write_text(json.dumps(profile))
    (tmp_path/'bad.json').write_text('{"name":"x","code":"import os"}')
    loaded, errors = load_plugins(tmp_path)
    assert len(loaded) == len(errors) == 1
    assert loaded[0]['timestamp'] == ['Time']
    assert 'bad.json' in errors[0]
    # A real structured signature; the catalog must never contain partial
    # fragments from quoted CSV header lines (e.g. Hayabusa).
    profile = detect_profile(['Timestamp','RuleTitle','Level','Computer','Channel','EventID','RecordID','Details','ExtraFieldInfo'])
    assert profile.name == 'HayabusaStandard'
    view, _ = profile_view(profile, ['Timestamp','RuleTitle','Level','Computer','Channel','EventID','RecordID','Details','ExtraFieldInfo'])
    assert view.timestamp_columns == [0]
    assert view.format_rules


def test_timestamp_presentation_keeps_submicrosecond_evidence():
    source = '2026-01-01T01:02:03.1234567+02:00'
    assert display_timestamp(source,'iso7') == '2026-01-01 01:02:03.1234567+02:00'
    assert display_timestamp(source,'source') == source
    assert display_timestamp('2026-01-01 01:02:03.123456789','iso7').endswith('.123456789')
    assert display_timestamp('invalid','iso7') == 'invalid'


def test_new_view_fields_roundtrip_and_invalid_sql_fields_fail_early(case):
    view = View(groups=[0], summaries=[Summary(2,'sum')], group_intervals={'0':'day'}, pinned_columns=[1], boolean_columns=[3], timestamp_columns=[0])
    assert View.from_json(view.to_json()) == view
    case.validate_view(view)
    view.summaries[0].operation = 'sum); DROP TABLE events; --'
    with pytest.raises(ValueError):
        case.validate_view(view)


def test_repeated_header_schemas_never_repeat_visual_column_indices():
    from fireblade.core.profile_catalog import CATALOG
    from fireblade.core.profiles import Profile
    for data in CATALOG:
        # DuckDB disambiguates source headers; emulate that public naming rule
        # to verify every advertised schema has a complete visual permutation.
        headers=[];seen=set()
        for name in data['signature']:
            candidate=name;number=1
            while candidate.casefold() in seen:
                candidate=name+'_'+str(number);number+=1
            headers.append(candidate);seen.add(candidate.casefold())
        profile=Profile(data['name'],tuple(data['signature']),tuple(data['timestamp']),tuple(data['columns']),tuple(data['booleans']))
        _view,order=profile_view(profile,headers)
        assert sorted(order)==list(range(len(headers))), data['name']


@pytest.mark.parametrize('encoding',['utf-8-sig','utf-16','cp1252'])
def test_powershell_type_metadata_only_skips_first_line(tmp_path,encoding):
    source=tmp_path/'history.csv'
    source.write_text('#TYPE System.Management.Automation.PSCustomObject\r\nUser,Command\r\nalice,Get-Process\r\n#TYPE kept,Get-Date\r\n',encoding=encoding,newline='')
    original=source.read_bytes()
    case=Case(tmp_path/'powershell.timeline')
    try:
        case.import_csv(source,encoding=encoding)
        assert case.headers==['User','Command']
        assert case.page(View())==[(1,'alice','Get-Process'),(2,'#TYPE kept','Get-Date')]
        assert source.read_bytes()==original
    finally:case.close()
