import csv
import hashlib
import shutil

import pytest

from scripts.qualify_large_replay import replay


def test_replay_keeps_quoted_multiline_records_and_only_one_bom_header(tmp_path,monkeypatch):
    source=tmp_path/'base.csv'
    payload='\ufeffName,Details\r\nalice,"first\nsecond"\r\nélève,"a,b"\r\n'.encode('utf-8')
    source.write_bytes(payload)
    monkeypatch.setattr(shutil,'disk_usage',lambda path:shutil._ntuple_diskusage(100*1024**3,0,100*1024**3))
    target=tmp_path/'replayed.csv'
    result=replay(source,target,hashlib.sha256(payload).hexdigest(),repeats=5)
    with target.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.reader(stream))
    assert rows==[['Name','Details']]+[['alice','first\nsecond'],['élève','a,b']]*5
    assert source.read_bytes()==payload
    assert result['sha256']==hashlib.sha256(target.read_bytes()).hexdigest()
    assert target.read_bytes().count(b'\xef\xbb\xbf')==1
    before=target.read_bytes()
    with pytest.raises(FileExistsError):replay(source,target,result['sha256'])
    assert target.read_bytes()==before


def test_failed_source_integrity_removes_only_the_new_replay(tmp_path,monkeypatch):
    monkeypatch.setattr(shutil,'disk_usage',lambda path:shutil._ntuple_diskusage(100*1024**3,0,100*1024**3))
    source=tmp_path/'source.csv';source.write_bytes(b'Name\noriginal\n')
    with pytest.raises(ValueError,match='SHA-256'):
        replay(source,tmp_path/'new.csv','0'*64,repeats=2)
    assert source.read_bytes()==b'Name\noriginal\n'
    assert not (tmp_path/'new.csv').exists()
