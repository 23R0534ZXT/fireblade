import csv
import hashlib
import pytest
from fireblade.core.engine import Case
from fireblade.core.models import View, Filter


@pytest.mark.parametrize('fmt,value,expected',[
    ('unix_s','0.123456789','1970-01-01T00:00:00.123456789Z'),
    ('unix_ms','1234.56789','1970-01-01T00:00:01.234567890Z'),
    ('unix_us','1234567','1970-01-01T00:00:01.234567000Z'),
    ('unix_ns','-1','1969-12-31T23:59:59.999999999Z'),
    ('filetime','116444736001234567','1970-01-01T00:00:00.123456700Z'),
    ('filetime','0','1601-01-01T00:00:00.000000000Z'),
    ('webkit','11644473600123456','1970-01-01T00:00:00.123456000Z'),
    ('dotnet','0','0001-01-01T00:00:00.000000000Z'),
    ('dotnet','3155378975999999999','9999-12-31T23:59:59.999999900Z'),
    ('ole','25569.5','1970-01-01T12:00:00.000000000Z'),
    ('ole','-1.25','1899-12-29T06:00:00.000000000Z'),
    ('iso','2026-01-01T01:02:03.123456789+02:00','2025-12-31T23:02:03.123456789Z'),
    ('mdy','01/02/2026 12:00:00','2026-01-02T12:00:00.000000000Z'),
    ('dmy','01/02/2026 12:00:00','2026-02-01T12:00:00.000000000Z'),
    ('iso','invalid',None),('unix_ns','999999999999999999999999999999999999999',None),
    ('iso','2026-01-01T00:00:00.1234567890Z',None),
])
def test_native_timestamp_conversions_preserve_precision(fmt,value,expected,tmp_path):
    source=tmp_path/'source.csv'
    with source.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['Time']);w.writerow([value])
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    case=Case(tmp_path/'test.timeline')
    try:
        case.import_csv(source)
        info=dict(case.info)
        case.add_derived_columns([dict(name='UTC',operation='timestamp',columns=['Time'],format=fmt)])
        assert case.page(View())[0][-1]==expected
        assert case.info==info and case.info['headers']==['Time']
        assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    finally:case.close()


def test_derived_columns_are_atomic_persistent_and_queryable(tmp_path):
    source=tmp_path/'source.csv';source.write_text('Ticks,Artifact\n116444736001234567,Prefetch\n0,LNK\nbad,Event Logs\n')
    case=Case(tmp_path/'test.timeline')
    try:
        case.import_csv(source)
        definitions=[dict(name='UTC',operation='timestamp',columns=['Ticks'],format='filetime'),
            dict(name='Category',operation='category',columns=['Artifact'],family='forensic'),
            dict(name='Text',operation='expression',expression="Concat([Artifact], '?')")]
        case.add_derived_columns(definitions)
        assert case.count(View(filters=[Filter(3,'eq','Execution')]))==1
        assert case.derived_quality([2])=={'UTC':(1,3)}
        original=case.page(View());headers=list(case.headers)
        with pytest.raises(ValueError):case.add_derived_columns([dict(name='Bad',operation='expression',expression="read_csv('x')")])
        assert case.headers==headers and case.page(View())==original
    finally:case.close()
    case=Case(tmp_path/'test.timeline')
    try:
        assert case.headers==headers and case.page(View())==original and case.derived==definitions
        assert case.page(View(sort_column=2,sort_type='timestamp'))[0][1]=='0'
        case.export(tmp_path/'out.csv',View(),columns=[2,3])
        assert '1970-01-01T00:00:00.123456700Z' in (tmp_path/'out.csv').read_text(encoding='utf-8-sig')
    finally:case.close()


@pytest.mark.parametrize('zone,expected',[('Europe/Paris','11'),('Romance Standard Time','11'),('+02:30','09'),('UTC-05:00','17')])
def test_named_windows_and_fixed_offset_timezones(tmp_path,zone,expected):
    source=tmp_path/'source.csv'
    with source.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['Date','Time','Zone']);w.writerow(['2026-01-01','12:00:00.123456789',zone])
    case=Case(tmp_path/'test.timeline')
    try:
        case.import_csv(source)
        case.add_derived_columns([dict(name='UTC',operation='timestamp',columns=['Date','Time'],timezone_column='Zone')])
        assert case.page(View())[0][-1]==f'2026-01-01T{expected}:30:00.123456789Z' if zone=='+02:30' else case.page(View())[0][-1]==f'2026-01-01T{expected}:00:00.123456789Z'
    finally:case.close()


def test_submicrosecond_sort_and_date_filter_respect_offsets(tmp_path):
    source=tmp_path/'source.csv';source.write_text('Time\n2026-01-01T00:00:00.123456799Z\n2026-01-01T01:00:00.123456700+01:00\n2026-01-01T00:00:00.123456701Z\n')
    case=Case(tmp_path/'test.timeline')
    try:
        case.import_csv(source)
        assert [r[0] for r in case.page(View(sort_column=0,sort_type='timestamp'))]==[2,3,1]
        assert [r[0] for r in case.page(View(filters=[Filter(0,'date_after','2026-01-01T00:00:00.123456701Z')]))]==[1]
    finally:case.close()
