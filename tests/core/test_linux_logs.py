"""Portable fixtures built from published format specifications, never host logs."""
import bz2
import csv
import gzip
import io
import json
import lzma
from pathlib import Path
import struct
import tarfile
import threading
import zipfile

import lz4.block
import lz4.frame
import pytest
import zstandard

from fireblade.core import linux_logs as linux
from fireblade.core.collection import Collection, ToolPack, identify, sha256
from fireblade.core.errors import OperationCancelled, cancellation_scope

LINE = b'Nov  3 12:00:00 host sshd[42]: Accepted password for alice from 192.0.2.1 port 22 ssh2\n'


def parsed(tmp_path, content, name='auth.log'):
    source = tmp_path/name
    source.write_bytes(content)
    output = tmp_path/'out'
    output.mkdir()
    result = linux.parse(source, output)
    rows = []
    for item in result['outputs']:
        with Path(item['csv']).open(encoding='utf-8', newline='') as stream:
            rows.extend(csv.DictReader(stream))
    return result, rows


@pytest.mark.parametrize('text,fmt,fields', [
    (LINE.decode().strip(), 'Syslog', {'PID':'42','Hôte':'host'}),
    ('2026-11-03T12:00:00+02:00 host app[2]: hello', 'Syslog', {'Détail':'hello'}),
    ('<34>1 2026-11-03T12:00:00Z host app 2 event [meta a="one two"] hello', 'Syslog RFC5424', {'PID':'2'}),
    ('type=SYSCALL msg=audit(1793707200.1:123): pid=42 ppid=1 uid=1000 exe="/bin/bash"', 'Linux audit', {'Événement':'123','Chemin':'/bin/bash'}),
    ('192.0.2.1 - alice [03/Nov/2026:12:00:00 +0000] "GET /index HTTP/1.1" 200 123 "-" "Agent"', 'HTTP access', {'Méthode':'GET','Chemin':'/index'}),
    ('2026/11/03 12:00:00 [error] 42#42: connection refused', 'Nginx error', {'PID':'42'}),
    ('[Tue Nov 03 12:00:00.000 2026] [core:error] [pid 42] missing', 'Apache error', {'Statut':'core:error'}),
    ('[ 123.456] usb connected', 'Kernel monotonic', {'Horodatage':'123.456'}),
    ('2026-11-03 12:00:00 startup packages', 'Application timestamp', {'Détail':'startup packages'}),
    ('{"@timestamp":"2026-11-03T12:00:00Z","message":"hello","pid":42,"extra":{"a":1}}', 'JSON Lines', {'PID':'42'}),
])
def test_text_formats(text,fmt,fields):
    row=linux.text_fields(text)
    assert row['Format']==fmt
    assert all(row[key]==value for key,value in fields.items())


@pytest.mark.parametrize('suffix,compress', [
    ('',lambda data:data),('.gz',gzip.compress),('.bz2',bz2.compress),
    ('.xz',lzma.compress),('.lzma',lambda data:lzma.compress(data,format=lzma.FORMAT_ALONE)),
    ('.zst',zstandard.ZstdCompressor().compress),('.lz4',lz4.frame.compress),
])
def test_rotations_and_raw_preservation(tmp_path,suffix,compress):
    content=LINE+b'unknown\ninvalid \xff\n'
    result, rows=parsed(tmp_path,compress(content),'auth.log.1'+suffix)
    assert result['structured']==1 and result['raw']==2
    assert rows[0]['Horodatage']=='Nov  3 12:00:00'
    assert rows[1]['Texte brut']=='unknown' and rows[2]['Texte brut']==r'invalid \xff'
    assert int(rows[1]['Offset'])==len(LINE)
    assert all(row['Source'].startswith(str(tmp_path/'auth.log.1')) for row in rows)


@pytest.mark.parametrize('compress,suffix',[(gzip.compress,'.gz'),(bz2.compress,'.bz2'),(lzma.compress,'.xz'),(zstandard.ZstdCompressor().compress,'.zst'),(lz4.frame.compress,'.lz4')])
def test_truncated_compression_is_reported(tmp_path,compress,suffix):
    data=compress(LINE*100)
    result,_=parsed(tmp_path,data[:-5],'auth.log'+suffix)
    assert any(m['status']=='error' for m in result['members'])
    assert result['warnings']


def test_xz_concatenation_padding_and_nested_compression(tmp_path):
    content=lzma.compress(LINE)+b'\0'*4+lzma.compress(LINE)
    result, rows=parsed(tmp_path,gzip.compress(content),'auth.log.xz.gz')
    assert len(rows)==2 and not result['warnings']


def test_tar_member_provenance_unsafe_paths_links_and_duplicates(tmp_path):
    memory=io.BytesIO()
    with tarfile.open(fileobj=memory,mode='w:gz') as archive:
        for name,data in [('var/log/auth.log',LINE),('var/log/auth.log',b'raw\n'),('../outside',b'bad')]:
            item=tarfile.TarInfo(name);item.size=len(data);archive.addfile(item,io.BytesIO(data))
        item=tarfile.TarInfo('var/log/link');item.type=tarfile.SYMTYPE;item.linkname='/tmp/escape';archive.addfile(item)
    result,rows=parsed(tmp_path,memory.getvalue(),'var-log.tar.gz')
    assert len(rows)==2 and rows[0]['Source']!=rows[1]['Source']
    assert sum(m['status']=='skipped' for m in result['members'])==2
    assert not (tmp_path.parent/'outside').exists()


def test_zip_members_are_read_without_extraction(tmp_path):
    memory=io.BytesIO()
    with zipfile.ZipFile(memory,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('var/log/auth.log',LINE)
        archive.writestr('../escape','bad')
    result,rows=parsed(tmp_path,memory.getvalue(),'var-log.zip')
    assert len(rows)==1 and any(m['status']=='skipped' for m in result['members'])


def test_zeek_and_w3c(tmp_path):
    data=b'#separator \\x09\n#fields\tts\tid.orig_h\tuid\n1793707200.25\t192.0.2.1\tabc\n#Fields: date time c-ip cs-method cs-uri-stem sc-status\n2026-11-03 12:00:00 192.0.2.2 POST /test 201\n'
    result,rows=parsed(tmp_path,data,'access.log')
    assert result['structured']==2
    assert rows[2]['Format']=='Zeek TSV' and rows[-1]['Statut']=='201'


@pytest.mark.parametrize('encoding', ['utf-16','utf-16-be','utf-32'])
def test_unicode_bom_logs(tmp_path,encoding):
    text='Nov  3 12:00:00 host app[42]: été\nunknown\n'
    bom={'utf-16-be':b'\xfe\xff'}.get(encoding,b'')
    result,rows=parsed(tmp_path,bom+text.encode(encoding))
    assert result['structured']==1 and result['raw']==1
    assert rows[0]['Détail']=='été' and rows[1]['Ligne']=='2'


def utmp():
    raw=bytearray(384)
    struct.pack_into('<h',raw,0,7);struct.pack_into('<i',raw,4,42)
    raw[8:13]=b'pts/0';raw[44:49]=b'alice';raw[76:80]=b'host'
    struct.pack_into('<ii',raw,340,1793707200,123)
    raw[348:352]=bytes([192,0,2,1])
    return bytes(raw)


def test_utmp_and_lastlog_fields_offsets_and_truncation(tmp_path):
    result,rows=parsed(tmp_path,utmp()+b'\0'*384+utmp(),'wtmp')
    assert result['structured']==2 and rows[1]['Offset']=='768'
    assert rows[0]['Adresse distante']=='192.0.2.1' and rows[0]['Utilisateur']=='alice'
    with pytest.raises(ValueError,match='tronqué'):
        list(linux.binary_rows(io.BytesIO(utmp()[:-1]),'wtmp'))
    raw=struct.pack('<i',1793707200)+b'pts/0'.ljust(32,b'\0')+b'host'.ljust(256,b'\0')
    rows=list(linux.binary_rows(io.BytesIO(b'\0'*292*3000+raw),'lastlog'))
    assert len(rows)==1 and rows[0]['UID']=='3000'


def journal_fixture(compact=False,compression=0):
    # Minimal object layout from systemd journal-def.h, with two DATA objects.
    header=bytearray(208);header[:8]=b'LPKSHHRH'
    struct.pack_into('<I',header,12,16 if compact else 0)
    struct.pack_into('<Q',header,88,len(header))
    objects=bytearray();references=[]
    for payload in (b'MESSAGE=hello',b'_PID=42'):
        if compression==1:payload=lzma.compress(payload)
        elif compression==2:payload=struct.pack('<Q',len(payload))+lz4.block.compress(payload,store_size=False)
        elif compression==4:payload=zstandard.ZstdCompressor().compress(payload)
        data=b'\0'*(56 if compact else 48)+payload
        obj=struct.pack('<BB6xQ',1,compression,16+len(data))+data
        references.append(len(header)+len(objects));objects.extend(obj);objects.extend(b'\0'*(-len(obj)%8))
    entry_offset=len(header)+len(objects)
    items=b''.join(struct.pack('<I',r) if compact else struct.pack('<QQ',r,0) for r in references)
    data=struct.pack('<QQQ',1,1793707200123456,123)+b'\0'*24+items
    objects.extend(struct.pack('<BB6xQ',3,0,16+len(data))+data)
    objects.extend(b'\0'*(-len(objects)%8))
    array_offset=len(header)+len(objects)
    array_data=struct.pack('<Q',0)+(struct.pack('<I',entry_offset) if compact else struct.pack('<Q',entry_offset))
    objects.extend(struct.pack('<BB6xQ',6,0,16+len(array_data))+array_data)
    struct.pack_into('<Q',header,176,array_offset)
    struct.pack_into('<Q',header,96,len(objects));struct.pack_into('<Q',header,136,array_offset)
    struct.pack_into('<Q',header,152,1)
    return bytes(header)+bytes(objects)


@pytest.mark.parametrize('compact',[False,True])
@pytest.mark.parametrize('compression',[0,1,2,4])
def test_systemd_standard_compact_and_compression(compact,compression):
    rows=list(linux.journal_rows(io.BytesIO(journal_fixture(compact,compression))))
    assert len(rows)==1 and rows[0]['Détail']=='hello' and rows[0]['PID']=='42'
    assert rows[0]['Horodatage']=='2026-11-03T12:00:00.123456+00:00'


@pytest.mark.parametrize('offset,value',[(12,128),(176,209),(152,2),(88,999999)])
def test_systemd_corruption_fails_explicitly(offset,value):
    fixture=bytearray(journal_fixture())
    struct.pack_into('<I' if offset==12 else '<Q',fixture,offset,value)
    with pytest.raises(ValueError):list(linux.journal_rows(io.BytesIO(fixture)))


def test_journal_export_repeated_binary_fields_and_truncation(tmp_path):
    binary=b'hello\nworld\0\xff'
    data=b'__CURSOR=test\n__REALTIME_TIMESTAMP=1793707200000000\nMESSAGE\n'+struct.pack('<Q',len(binary))+binary+b'\nKEY=a\nKEY=b\n\n'
    result,rows=parsed(tmp_path,data)
    assert result['structured']==1 and rows[0]['Détail']==r'hello'+ '\nworld\0'+r'\xff'
    assert json.loads(rows[0]['Champs'])['KEY']==['a','b']
    with pytest.raises(ValueError):list(linux.export_rows(io.BytesIO(data[:-15])))


@pytest.mark.parametrize('limit,value,data,name',[
    ('MAX_LINE',16,LINE,'auth.log'),('MAX_DEPTH',0,gzip.compress(LINE),'auth.log.gz'),
    ('MAX_EXPANDED',10,LINE,'auth.log'),('MAX_MEMBERS',0,LINE,'auth.log'),
])
def test_limits_are_explicit(tmp_path,monkeypatch,limit,value,data,name):
    monkeypatch.setattr(linux,limit,value)
    try:result,_=parsed(tmp_path,data,name)
    except ValueError:return
    assert any(m['status']=='error' for m in result['members'])


def test_cancel_and_source_integrity(tmp_path):
    source=tmp_path/'auth.log';source.write_bytes(LINE);before=sha256(source)
    output=tmp_path/'out';output.mkdir()
    cancelled=threading.Event();cancelled.set()
    with cancellation_scope(cancelled),pytest.raises(OperationCancelled):linux.parse(source,output)
    assert sha256(source)==before


def test_real_collection_import_and_linux_profile(tmp_path):
    root=tmp_path/'evidence'/'var'/'log';root.mkdir(parents=True)
    source=root/'custom';source.write_bytes(LINE)
    assert identify(source)==['LinuxLogs']
    collection=Collection(root,tmp_path/'work',ToolPack(tmp_path/'none'),organization='combined')
    result=collection.parse()
    assert result['status']=='complete' and result['files'][0]['status']=='complete'
    assert result['files'][0]['runs'][0]['linux_logs']['structured']==1
    assert len(result['documents'])==1


def test_payload_enrichment_and_explicit_utc(tmp_path):
    audit=b'type=EXECVE msg=audit(1793707200.125:123): argc=1 exe=2F62696E2F7368 comm="sh" proctitle=7368002D63006964\n'
    ufw=b'Nov  3 12:00:00 host kernel: [UFW BLOCK] SRC=192.0.2.1 DST=198.51.100.1 PROTO=TCP SPT=123 DPT=22\n'
    result,rows=parsed(tmp_path,LINE+audit+ufw)
    assert rows[0]['Événement']=='SSH Accepted' and rows[0]['Utilisateur']=='alice'
    assert rows[0]['Horodatage UTC']==''
    assert rows[1]['Chemin']=='/bin/sh' and rows[1]['Horodatage UTC']=='2026-11-03T12:00:00.125000+00:00'
    assert rows[1]['Commande']=='sh ␀ -c ␀ id' and rows[1]['Clé de corrélation'].endswith(':123')
    assert rows[2]['Port destination']=='22' and rows[2]['Adresse source']=='192.0.2.1'


def test_cef_and_sudo(tmp_path):
    cef=b'Nov  3 12:00:00 host app: CEF:0|Acme|Tool|1|42|Login|5|src=192.0.2.1 suser=alice msg=hello world\n'
    sudo=b'Nov  3 12:00:00 host sudo: alice : TTY=pts/0 ; PWD=/home/alice ; USER=root ; COMMAND=/usr/bin/id\n'
    result,rows=parsed(tmp_path,cef+sudo)
    assert rows[0]['Format']=='CEF' and rows[0]['Adresse source']=='192.0.2.1'
    assert json.loads(rows[0]['Champs'])['extension']['msg']=='hello world'
    assert rows[1]['Commande']=='/usr/bin/id' and rows[1]['Utilisateur cible']=='root'


def test_orphaned_systemd_entry_is_not_imported():
    data=bytearray(journal_fixture())
    orphan=struct.pack('<BB6xQ',3,0,64)+b'\0'*48
    data.extend(b'\0'*(-len(data)%8));data.extend(orphan)
    struct.pack_into('<Q',data,96,len(data)-208)
    assert len(list(linux.journal_rows(io.BytesIO(data))))==1


def test_zip_index_limits_are_checked_before_open(tmp_path,monkeypatch):
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as archive:archive.writestr('auth.log',LINE)
    monkeypatch.setattr(linux,'MAX_OBJECT',4)
    result,rows=parsed(tmp_path,data.getvalue(),'var-log.zip')
    assert not rows and 'Index ZIP' in result['members'][0]['reason']


def test_zstd_concatenated_frames(tmp_path):
    compressor=zstandard.ZstdCompressor()
    result,rows=parsed(tmp_path,compressor.compress(LINE)+compressor.compress(LINE),'auth.log.zst')
    assert len(rows)==2 and not result['warnings']


@pytest.mark.parametrize('endian,version',[('<',3),('>',131)])
def test_linux_process_accounting(tmp_path,endian,version):
    raw=struct.pack('BB',0,version)+struct.pack(endian+'H6If8H',0,0,1000,1000,42,1,1793707200,1.5,*range(8))+b'command'.ljust(16,b'\0')
    result,rows=parsed(tmp_path,gzip.compress(raw),'pacct.1.gz')
    assert result['structured']==1 and rows[0]['PID']=='42' and rows[0]['Commande']=='command'
    assert rows[0]['UID']=='1000' and json.loads(rows[0]['Champs'])['elapsed_seconds']==1.5


def test_log1_inside_var_log_is_not_dropped(tmp_path):
    root=tmp_path/'var'/'log';root.mkdir(parents=True)
    source=root/'custom.log1';source.write_bytes(LINE)
    assert identify(source)==['LinuxLogs']


@pytest.mark.parametrize('value,epoch,expected',[
    ('1793707200.123456789',True,'2026-11-03T12:00:00.123456789+00:00'),
    ('-0.125',True,'1969-12-31T23:59:59.875000+00:00'),
    ('2026-11-03T14:00:00.123456789+02:00',False,'2026-11-03T12:00:00.123456789+00:00'),
    ('2026-11-03T12:00:00',False,''),('bad',True,''),
])
def test_normalization_preserves_nanoseconds_without_timezone_guess(value,epoch,expected):
    from fireblade.core.linux_log_formats import utc_time
    assert utc_time(value,epoch)==expected


@pytest.mark.parametrize('encoding',['utf-16','utf-32'])
def test_long_unicode_line_crosses_buffers_without_offset_loss(tmp_path,encoding):
    first='Nov  3 12:00:00 host app[42]: '+'é'*40000+'\n'
    data=(first+'raw\n').encode(encoding)
    _,rows=parsed(tmp_path,data)
    assert rows[0]['Détail']=='é'*40000
    assert int(rows[1]['Offset'])==len(first.encode(encoding))


@pytest.mark.parametrize('seed',range(20))
def test_generated_unknown_text_round_trips_without_loss(tmp_path,seed):
    import random
    generator=random.Random(seed)
    lines=['unknown '+''.join(generator.choice('abcé,;\t"\\=') for _ in range(100)) for _ in range(10)]
    _,rows=parsed(tmp_path,gzip.compress(('\n'.join(lines)+'\n').encode()),'custom.log.gz')
    assert [row['Texte brut'] for row in rows]==lines
    assert all(row['Lecture']=='Brute' for row in rows)


def test_partial_journal_corruption_keeps_rows_and_exposes_error(tmp_path):
    data=bytearray(journal_fixture())
    array_offset,=struct.unpack_from('<Q',data,176)
    struct.pack_into('<Q',data,array_offset+16,array_offset)
    result,rows=parsed(tmp_path,bytes(data),'system.journal')
    assert len(rows)==1 and result['warnings']
    assert any(m['status']=='error' and 'Cycle' in m['reason'] for m in result['members'])


def test_utc_and_ip_columns_are_usable_by_timeline():
    from fireblade.core.timeline import field_kind,guess_time_column
    assert linux.HEADERS[guess_time_column(linux.HEADERS)]=='Horodatage UTC'
    assert field_kind('Adresse distante')=='ip' and field_kind('Adresse source')=='ip'


def test_rfc5424_structured_data_escaping_and_invalid_priority():
    sd=r'[meta x="a\]b" y="c\\d"][other k="v"]'
    row=linux.text_fields('<34>1 2026-11-03T12:00:00Z host app 42 event '+sd+' hello')
    assert row['Détail']=='hello' and json.loads(row['Champs'])['structured_data']==sd
    assert not linux.text_fields('<999>1 - host app 42 event - hello')
    assert not linux.text_fields('<34>1 - host app 42 event [truncated')


def test_zstandard_large_window_and_empty_frame():
    from fireblade.core.linux_streams import StrictZstd
    content=b'A'*(1024*1024)
    for data in (content,b''):
        with io.BufferedReader(StrictZstd(io.BytesIO(zstandard.ZstdCompressor().compress(data)))) as reader:
            assert reader.read()==data


def test_valid_utmp_prefix_survives_trailing_truncation(tmp_path):
    result,rows=parsed(tmp_path,utmp()+b'x','wtmp')
    assert len(rows)==1 and result['warnings'] and result['members'][0]['status']=='error'


def test_sudo_command_semicolons_and_malformed_payload(tmp_path):
    line=b'Nov  3 12:00:00 host sudo: alice : TTY=x ; PWD=/tmp ; USER=root ; COMMAND=/bin/sh -c id;whoami\n'
    _,rows=parsed(tmp_path,line)
    assert rows[0]['Commande']=='/bin/sh -c id;whoami'
    malformed=b'Nov  3 12:00:00 host sudo: alice : TTY=x ; PWD='+b' '*100000+b'COMMAND=x\n'
    from fireblade.core.linux_log_formats import enrich
    assert 'Commande' not in enrich({'Détail':malformed.decode()},malformed.decode())


@pytest.mark.parametrize('compress,suffix',[(bz2.compress,'.bz2'),(lz4.frame.compress,'.lz4')])
def test_compressed_trailing_garbage_is_not_silently_ignored(tmp_path,compress,suffix):
    result,rows=parsed(tmp_path,compress(LINE)+b'not another frame','auth.log'+suffix)
    assert result['warnings'] and any(m['status']=='error' for m in result['members'])


@pytest.mark.parametrize('compress,suffix',[(bz2.compress,'.bz2'),(lz4.frame.compress,'.lz4')])
def test_bz2_lz4_concatenated_frames(tmp_path,compress,suffix):
    result,rows=parsed(tmp_path,compress(LINE)+compress(LINE),'auth.log'+suffix)
    assert len(rows)==2 and not result['warnings']
