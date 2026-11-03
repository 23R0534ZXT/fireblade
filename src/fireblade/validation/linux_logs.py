"""Portable Linux log corpus and desktop/frozen-app acceptance check."""
import bz2
import gzip
import io
import lzma
from pathlib import Path
import struct
import time
import zipfile

import lz4.frame
import zstandard


def journal_sample():
    header=bytearray(208);header[:8]=b'LPKSHHRH'
    payload=b'MESSAGE=Linux journal acceptance'
    data=struct.pack('<BB6xQ',1,0,64+len(payload))+b'\0'*48+payload
    data+=b'\0'*(-len(data)%8)
    entry_offset=208+len(data)
    entry=struct.pack('<BB6xQ',3,0,80)+struct.pack('<QQQ',1,1793707200000000,0)+b'\0'*24+struct.pack('<QQ',208,0)
    array_offset=entry_offset+len(entry)
    array=struct.pack('<BB6xQQQ',6,0,32,0,entry_offset)
    objects=data+entry+array
    for offset,value in [(88,208),(96,len(objects)),(136,array_offset),(144,3),(152,1),(176,array_offset)]:
        struct.pack_into('<Q',header,offset,value)
    return bytes(header)+objects


def write_corpus(directory):
    directory=Path(directory)/'var'/'log';directory.mkdir(parents=True)
    line=b'2026-11-03T12:00:00Z host sshd[42]: Accepted password for alice from 192.0.2.1 port 22 ssh2\n'
    compressors=[('',lambda data:data),('.gz',gzip.compress),('.bz2',bz2.compress),('.xz',lzma.compress),
                 ('.zst',zstandard.ZstdCompressor().compress),('.lz4',lz4.frame.compress)]
    for suffix,compress in compressors:(directory/('auth.log'+suffix)).write_bytes(compress(line))
    (directory/'unicode.log').write_bytes(line.decode().encode('utf-16'))
    (directory/'system.journal').write_bytes(journal_sample())
    raw=bytearray(384);struct.pack_into('<h',raw,0,7);struct.pack_into('<i',raw,4,42)
    struct.pack_into('<ii',raw,340,1793707200,0);raw[44:49]=b'alice'
    (directory/'wtmp').write_bytes(raw)
    (directory/'audit.log').write_bytes(b'type=EXECVE msg=audit(1793707200.125:123): pid=42 exe=2F62696E2F7368\n')
    with zipfile.ZipFile(directory/'logs.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('var/log/auth.log',line)
    (directory/'unknown.log').write_bytes(b'unknown application continuation\n')
    return directory


def verify_linux_logs(app,directory,settings=None):
    from fireblade.core.collection import Collection,ToolPack,sha256
    from fireblade.core.models import Filter,View
    from fireblade.ui.app import Window
    directory=Path(directory);source=write_corpus(directory/'evidence')
    originals={p:sha256(p) for p in source.iterdir()}
    errors=[];window=Window(require_case=False, settings=settings,investigation_root=directory/'cases')
    window.error=lambda value:errors.append(str(value));window.show()
    def settle():
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            app.processEvents()
            if not window.busy and not window.jobs and not window.pool.activeThreadCount() and not getattr(window,'_collection_open_pending',False) and (window.model is None or not window.model.jobs) and not window.tabs.pending:
                assert not errors,errors
                return
            time.sleep(.005)
        raise AssertionError('Linux log UI did not settle')
    try:
        investigation=window.create_investigation('Qualification journaux Linux',environment='linux')
        assert investigation,errors
        collection=Collection(source,window.investigation_data_directory('Collectes')/'linux-logs',ToolPack(directory/'no-engines'),settings,organization='artifacts')
        report=collection.parse()
        runs=[r for item in report['files'] for r in item.get('runs',[])]
        assert report['status']=='complete' and len(runs)==12
        assert all(r['tool']=='LinuxLogs' and r['status'] in ('complete','complete_with_warnings') for r in runs)
        assert sum(r['linux_logs']['structured'] for r in runs)==11
        assert sum(r['linux_logs']['raw'] for r in runs)==1
        window.collection=collection;window.collection_finished(report);settle()
        assert len(window.documents)==1 and window.case.count(View())==12
        assert window.case.count(View(filters=[Filter(window.case.headers.index('PID'),'eq','42')]))==10
        assert window.model.rowCount()==12
        window.case.bookmark(1,'Note LinuxLogs')
        saved_path=window.case.path
        assert window.close_investigation()
        assert window.open_investigation(investigation['id']);settle()
        assert window.case.path==saved_path and window.case.bookmarks()=={1:'Note LinuxLogs'}
        assert all(sha256(p)==value for p,value in originals.items())
        window.grab().save(str(directory/'linux-log-desktop.png'))
        return dict(status='passed',source_files=12,structured=11,raw=1,rows=12,
                    source_files_unchanged=True,case_restored=True,compression_modules_bundled=True)
    finally:
        window.close();window.deleteLater()
