import csv
from decimal import Decimal
import pytest
from fireblade.core.engine import Case
from fireblade.core.models import View, Summary, Filter


def test_complete_outline_matches_recursive_queries_and_pages_beyond_first_groups(tmp_path):
    source=tmp_path/'s.csv'
    with source.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['A','B','N'])
        for i in range(103):w.writerow([f'g{i%31:02}',f's{i%3}',str(i)])
    case=Case(tmp_path/'c.timeline')
    try:
        case.import_csv(source)
        for ordering in ('count','value','summary'):
            view=View(groups=[0,1],summaries=[Summary(2,'sum')],group_order=ordering,group_descending=False,filters=[Filter(2,'ge','4')])
            expected=[]
            def walk(path=()):
                for row in case.page(view,path,limit=250):
                    group=len(path)<2
                    next_path=path+(row[0],) if group else ()
                    expected.append(dict(group=group,path=next_path,values=row))
                    if group:walk(next_path)
            walk()
            actual=[]
            for offset in range(0,len(expected)+25,25):actual.extend(case.outline_page(view,offset,25))
            assert actual==expected
            assert len([r for r in actual if not r['group']])==99
            assert any(r['path']==('g30',) for r in actual if r['group'])
            assert case._outline_key is not None
            assert not [r for r in case.db.execute('SHOW TABLES').fetchall() if r[0].startswith('__outline_')]
    finally:case.close()


def test_outline_null_paths_precision_and_bookmark_invalidation(tmp_path):
    source=tmp_path/'s.csv';source.write_text('A,N\n,9007199254740993\nx,2\nx,3\n')
    case=Case(tmp_path/'c.timeline')
    try:
        case.import_csv(source)
        view=View(groups=[0],summaries=[Summary(1,'sum')],bookmarks_only=True)
        case.bookmark(1,'note')
        first=case.outline_page(view)
        assert first[0]['path']==(None,) and first[0]['values'][2]==Decimal('9007199254740993')
        assert len(first)==2
        case.bookmark(2,'other')
        assert len(case.outline_page(view))==4
        assert case.outline_page(View(groups=[0],filters=[Filter(0,'eq','missing')]))==[]
    finally:case.close()


def test_cancel_outline_cleans_staging_and_preserves_previous_index(tmp_path):
    from fireblade.core.errors import OperationCancelled
    source=tmp_path/'s.csv';source.write_text('A,B\nx,y\nx,z\n')
    case=Case(tmp_path/'c.timeline')
    try:
        case.import_csv(source);old=View(groups=[0]);expected=case.outline_page(old)
        def cancel(_):case.interrupt()
        with pytest.raises(OperationCancelled):case.outline_page(View(groups=[0,1]),progress=cancel)
        assert not [r for r in case.db.execute('SHOW TABLES').fetchall() if r[0].startswith('__outline_')]
        assert case.outline_page(old)==expected
    finally:case.close()


def test_complete_outline_spills_under_a_64_mb_budget_without_path_arrays(tmp_path):
    # SQL-only fixture: no new large CSV is generated. A million narrow source
    # rows force the hierarchy beyond a small in-memory sort workspace.
    case=Case(tmp_path/'spill.timeline',memory_mb=64,threads=1)
    try:
        case.db.execute("CREATE TABLE events AS SELECT i+1 AS __row_id,'g'||cast(i%7 AS VARCHAR) AS c0,'u'||cast(i%100 AS VARCHAR) AS c1,'h'||cast(i%24 AS VARCHAR) AS c2,cast(i AS VARCHAR) AS c3 FROM range(1000000) t(i)")
        case.headers=['Group','User','Host','N'];case.info={'rows':1000000,'headers':list(case.headers)}
        view=View(groups=[0,1,2],summaries=[Summary(3,'sum')],group_order='value',group_descending=False)
        assert len(case.outline_page(view))==250
        count,distinct,minimum,maximum=case.db.execute('SELECT count(*),count(DISTINCT position),min(position),max(position) FROM __fireblade_outline').fetchone()
        assert count==distinct==maximum and minimum==1
        assert case.db.execute('SELECT count(*),count(DISTINCT row_id) FROM __fireblade_outline WHERE depth=0').fetchone()==(1000000,1000000)
        assert len(case.outline_page(view,offset=500000))==250
        assert case.db.execute("SELECT current_setting('preserve_insertion_order')").fetchone()[0]
        from fireblade.core.derived import timestamp_sql
        utc=timestamp_sql('c3','unix_ns')
        assert case.db.execute(f'SELECT count(*) FILTER (WHERE ({utc}) IS NULL),count(*) FROM events').fetchone()==(0,1000000)
    finally:case.close()


@pytest.mark.parametrize("before",[False,True])
def test_source_id_index_follows_derived_storage_and_can_be_disabled(tmp_path,before):
    source=tmp_path/'s.csv';source.write_text('A,N\nx,1\nx,2\ny,3\n')
    case=Case(tmp_path/'i.timeline')
    try:
        case.import_csv(source)
        if before:assert case.outline_page(View(groups=[0]))
        case.add_derived_columns([dict(name='N2',operation='expression',expression='[N]*2')])
        assert Decimal(case.outline_page(View(groups=[0]))[1]['values'][-1])==2
        assert case.db.execute("SELECT table_name FROM duckdb_indexes() WHERE index_name='__fireblade_source_id'").fetchone()==('__fireblade_source_events',)
        assert case.info['headers']==['A','N']
    finally:case.close()
    from fireblade.core.settings import Settings
    case=Case(tmp_path/'no-index.timeline',settings=Settings(cache_sorted_pages=False))
    try:
        case.import_csv(source);assert case.outline_page(View(groups=[0]))
        assert not case.db.execute("SELECT * FROM duckdb_indexes() WHERE index_name='__fireblade_source_id'").fetchall()
    finally:case.close()
