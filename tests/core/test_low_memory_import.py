import csv
import hashlib

import pytest
from fireblade.core.engine import Case
from fireblade.core.models import View,Filter
from fireblade.core.settings import Settings
from fireblade.core.errors import OperationCancelled


def wide_source(path, rows=24):
    values=['comma,semi;','quoted "value"','line\nnext','évidence','', 'NULL']
    expected=[[values[(column+row)%len(values)] for column in range(400)] for row in range(rows)]
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream,delimiter=';');writer.writerow([f'Field {i}' for i in range(400)]);writer.writerows(expected)
    return [[None if value=='' else value for value in row] for row in expected]


def test_wide_parser_csv_retries_under_64mb_and_preserves_every_cell(tmp_path):
    source=tmp_path/'wide.csv';expected=wide_source(source)
    digest=hashlib.sha256(source.read_bytes()).hexdigest();progress=[]
    case=Case(tmp_path/'wide.timeline',settings=Settings(memory_mb=64,threads=1))
    try:
        info=case.import_csv(source,delimiter=';',progress=progress.append)
        assert info['rows']==len(expected)
        assert 'Import à mémoire réduite…' in progress
        assert [list(row[1:]) for row in case.page(View())]==expected
        assert [list(row[1:]) for row in case.page(View(filters=[Filter(0,'eq','évidence')]))]==[row for row in expected if row[0]=='évidence']
        assert len(case.page(View(search='quoted')))==len(expected)
        assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
        assert case.db.execute("SELECT current_setting('memory_limit')").fetchone()[0]=='61.0 MiB'
    finally:case.close()


def test_cancelling_fallback_rolls_back_every_insert(tmp_path):
    source=tmp_path/'wide.csv';wide_source(source,150)
    case=Case(tmp_path/'wide.timeline',settings=Settings(memory_mb=64,threads=1))
    def cancel(message):
        if '64 enregistrements' in message:case.cancelled.set()
    try:
        with pytest.raises(OperationCancelled):case.import_csv(source,delimiter=';',progress=cancel)
        assert case.db.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='events'").fetchone()[0]==0
        assert not case.headers
    finally:case.close()


def test_fallback_also_handles_schema_probe_memory_exhaustion(tmp_path):
    import duckdb
    source=tmp_path/'source.csv';source.write_text('Name;Value\nalice;001\nbob;002\n')
    case=Case(tmp_path/'probe.timeline',settings=Settings(memory_mb=64,threads=1))
    connection=case.db
    class ProbeFailure:
        def __getattr__(self,name):return getattr(connection,name)
        def read_csv(self,*a,**k):raise duckdb.OutOfMemoryException('CSV sample too large')
    case.db=ProbeFailure()
    try:
        case.import_csv(source)
        assert case.page(View())==[(1,'alice','001'),(2,'bob','002')]
    finally:case.close()
