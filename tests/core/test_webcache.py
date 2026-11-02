import csv
from datetime import datetime,timezone
import gzip
import hashlib
import json
from pathlib import Path
import threading

import pytest

from fireblade.core.collection import Collection,ToolPack,identify,sha256
from fireblade.core.errors import OperationCancelled,cancellation_scope
from fireblade.core.engine import Case
from fireblade.core.models import View,Filter
from fireblade.core.webcache import cell,filetime,parse


@pytest.fixture
def webcache_source(tmp_path):
    fixtures=Path(__file__).parents[1]/'fixtures'/'browser-artifacts'
    target=tmp_path/'WebCacheV01.dat';target.write_bytes(gzip.decompress((fixtures/'WebCacheV01.dat.gz').read_bytes()))
    entry=next(item for item in json.loads((fixtures/'SOURCES.json').read_text()) if item['tool']=='WebCache')
    assert sha256(target)==entry['sha256']
    return target


def test_filetime_retains_exact_100_nanoseconds_and_sentinels():
    assert filetime(130443534661252928)=='2014-05-12T07:31:06.1252928Z'
    assert filetime(1)=='1601-01-01T00:00:00.0000001Z'
    assert all(filetime(value)=='' for value in [None,0,-1,0xffffffffffffffff])
    for value in [-2,'123',True,1.1]:
        with pytest.raises(ValueError):filetime(value)
    with pytest.raises(OverflowError):filetime(2**64-2)


def test_cell_fidelity_for_large_identifiers_binary_and_multi_values():
    assert cell(18446744073709551614)=='18446744073709551614'
    assert cell(b'\x00\xff')=='hex:00ff'
    assert json.loads(cell([b'\xff',None,42]))==['hex:ff',None,42]
    assert cell('évidence\n=1+1')=='évidence\n=1+1'


def test_real_webcache_exports_urls_container_names_and_exact_times(webcache_source,tmp_path):
    output=tmp_path/'output';output.mkdir();before=sha256(webcache_source)
    report=parse(webcache_source,output)
    assert report['rows']==1612 and report['warnings']==[] and len(report['outputs'])==23
    rows=[]
    for item in report['outputs']:
        with Path(item['csv']).open(encoding='utf-8',newline='') as stream:rows.extend(csv.DictReader(stream))
    row=next(row for row in rows if row.get('Url')=='Visited: test@http://code.google.com/p/libyal/wiki/Overview')
    assert row['WebCache_Container']=='History' and row['WebCache_RecordType']=='CacheEntry'
    assert row['AccessedTime']=='130443534661252928'
    assert row['AccessedTime_UTC']=='2014-05-12T07:31:06.1252928Z'
    assert row['ResponseHeaders'].startswith('hex:')
    appcache=[row for row in rows if row['WebCache_Table']=='AppCacheEntry_1']
    assert len(appcache)==12 and all(row['WebCache_RecordType']=='AppCacheEntry' for row in appcache)
    dependencies=[row for row in rows if row['WebCache_Table'].startswith('DependencyEntry_')]
    assert dependencies and all(row['WebCache_RecordType']=='DependencyEntry' for row in dependencies)
    assert sha256(webcache_source)==before


@pytest.mark.parametrize('mode',['files','artifacts','combined'])
def test_real_webcache_collection_import_and_filter(webcache_source,tmp_path,mode):
    root=tmp_path/'evidence';root.mkdir();webcache_source.rename(root/webcache_source.name)
    collection=Collection(root,tmp_path/'work',ToolPack(tmp_path/'no-pack'),organization=mode)
    report=collection.parse()
    assert report['files'][0]['tools']==['WebCache'] and report['files'][0]['status']=='complete'
    total=0;found=False
    for document in report['documents']:
        case=Case(document['path'])
        try:
            total+=case.count(View())
            if 'Url' in case.headers:
                found=found or case.count(View(filters=[Filter(case.headers.index('Url'),'contains','code.google.com/p/libyal')]))>0
            if mode=='combined':assert document['view']['groups']==[0]
        finally:case.close()
    assert total==1612 and found
    if mode!='files':assert len(report['documents'])==1


def test_invalid_named_webcache_is_reported_not_silently_ignored(tmp_path):
    root=tmp_path/'evidence';root.mkdir();path=root/'WebCacheV01.dat';path.write_bytes(b'invalid ESE data')
    assert identify(path)==['WebCache']
    report=Collection(root,tmp_path/'work',ToolPack(tmp_path/'no-pack')).parse()
    assert report['files'][0]['status']=='attention' and report['files'][0]['runs'][0]['status']=='error'
    assert not report['documents']


def test_cancellation_checks_before_creating_records(webcache_source,tmp_path):
    event=threading.Event();event.set()
    with cancellation_scope(event),pytest.raises(OperationCancelled):parse(webcache_source,tmp_path)


def test_dirty_database_and_unreadable_table_are_reported(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import dissect.esedb
    class Table:
        def __init__(self,name,rows=None):self.name=name;self.rows=rows;self.columns=[]
        def records(self):
            if self.rows is None:raise ValueError('damaged page')
            return iter(self.rows)
    class Database:
        header=SimpleNamespace(dbstate=2)
        def __init__(self,*args):pass
        def tables(self):return [Table('Containers',[]),Table('Container_1')]
    monkeypatch.setattr(dissect.esedb,'EseDB',Database)
    source=tmp_path/'WebCacheV01.dat';source.touch();output=tmp_path/'out';output.mkdir()
    report=parse(source,output)
    assert report['database_state']==2 and report['warning_count']==2 and not report['outputs']
    assert any('sans rejeu' in warning for warning in report['warnings'])
    assert next(table for table in report['tables'] if table['table']=='Container_1')['status']=='error'


def test_ese_without_webcache_schema_is_rejected(tmp_path,monkeypatch):
    import dissect.esedb
    class Database:
        def __init__(self,*args):pass
        def tables(self):return []
    monkeypatch.setattr(dissect.esedb,'EseDB',Database)
    source=tmp_path/'input.dat';source.touch()
    with pytest.raises(ValueError,match='schéma WebCache'):parse(source,tmp_path)
