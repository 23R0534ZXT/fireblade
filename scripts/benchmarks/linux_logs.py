"""Linux log stress and end-to-end qualification; no publication.

The large-source phase verifies/hashes decoded records with CSV serialization
bypassed to avoid retaining twice the expanded volume. The separate collection phase persists and
reopens real DuckDB analyses. These are distinct measurements in the report.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import time
from unittest.mock import patch

import psutil
import zstandard

from fireblade.core import linux_logs
from fireblade.core.collection import Collection, ToolPack, sha256
from fireblade.core.engine import Case
from fireblade.core.models import View


class DigestSink:
    def __init__(self):
        self.digest=hashlib.sha256();self.bytes=0;self.lines=0
    def write(self,value):
        data=value.encode('utf-8');self.digest.update(data);self.bytes+=len(data);self.lines+=value.count('\n')
        return len(value)
    def close(self):
        pass


def qualify(directory, gib=32, import_rows=200000):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    report={'format':'fireblade-linux-log-qualification','version':1,
            'time':datetime.now(timezone.utc).isoformat(),'large_record_stream_mode':'decoded records verified and hashed; CSV serialization bypassed; no DuckDB import in this phase'}
    process=psutil.Process();peak=[process.memory_info().rss];stop=threading.Event()
    def monitor():
        while not stop.wait(.05):peak[0]=max(peak[0],process.memory_info().rss)
    watcher=threading.Thread(target=monitor,daemon=True);watcher.start()
    try:
        with tempfile.TemporaryDirectory(prefix='linux-stress-',dir=directory) as folder:
            folder=Path(folder);source=folder/'syslog.zst';out=folder/'out';out.mkdir()
            prefix=b'2026-11-03T12:00:00Z host app[42]: '
            block=prefix+b'A'*(1024*1024-len(prefix)-1)+b'\n'
            count=int(gib*1024)
            expanded_hash=hashlib.sha256()
            with source.open('wb') as stream,zstandard.ZstdCompressor(level=1).stream_writer(stream) as compressor:
                for _ in range(count):
                    compressor.write(block);expanded_hash.update(block)
            source_hash=sha256(source);sink=DigestSink();observed=[0]
            decoded_hash=hashlib.sha256();decoded_bytes=[0]
            expected_raw=block[:-1].decode();expected_detail='A'*(len(block)-len(prefix)-1)
            original_open=Path.open;original_writer=csv.DictWriter
            def open_output(path,*args,**kwargs):
                return sink if path==out/'Linux — journaux.csv' else original_open(path,*args,**kwargs)
            class CheckedWriter(original_writer):
                def writerow(self,row):
                    if row.get('Lecture') in ('Structurée','Brute'):
                        index=observed[0]
                        assert row['Texte brut']==expected_raw
                        assert row['Détail']==expected_detail
                        assert row['PID']=='42' and row['Ligne']==str(index+1)
                        assert row['Offset']==str(index*len(block))
                        value=row['Texte brut'].encode('utf-8')
                        decoded_hash.update(value);decoded_hash.update(b'\n');decoded_bytes[0]+=len(value)+1
                        observed[0]+=1
                        if observed[0] % 1024 == 0:
                            print(f'Linux stress: {observed[0]//1024} GiB / {count//1024} GiB',flush=True)
                        return None
                    return super().writerow(row)
            start=time.monotonic()
            with patch.object(Path,'open',open_output),patch.object(csv,'DictWriter',CheckedWriter):
                result=linux_logs.parse(source,out)
            duration=time.monotonic()-start
            assert observed[0]==count==result['structured'] and not result['raw'] and not result['warnings'], (observed[0],result)
            assert decoded_bytes[0]==len(block)*count and decoded_hash.digest()==expanded_hash.digest()
            assert sha256(source)==source_hash
            report['large_source']={'expanded_bytes':len(block)*count,'compressed_bytes':source.stat().st_size,
                                    'source_sha256':source_hash,'records_checked':observed[0],
                                    'decoded_bytes_hashed':decoded_bytes[0],'decoded_sha256':decoded_hash.hexdigest(),
                                    'seconds':duration,'mib_per_second':len(block)*count/1024**2/duration,
                                    'peak_rss_bytes':peak[0]}
        peak[0]=process.memory_info().rss
        with tempfile.TemporaryDirectory(prefix='linux-import-',dir=directory) as folder:
            folder=Path(folder);root=folder/'evidence'/'var'/'log';root.mkdir(parents=True)
            source=root/'auth.log'
            with source.open('wb') as stream:
                for number in range(import_rows):
                    stream.write(f'2026-11-03T12:00:00Z host sshd[42]: Accepted password for user{number} from 192.0.2.1 port 22 ssh2\n'.encode())
            before=sha256(source);start=time.monotonic()
            collection=Collection(root,folder/'work',ToolPack(folder/'none'),organization='artifacts')
            result=collection.parse()
            assert result['status']=='complete' and all(e['status']=='complete' for e in result['files'])
            assert len(result['documents'])==1
            case=Case(result['documents'][0]['path'])
            try:
                assert case.count(View())==import_rows
                assert case.db.execute('SELECT count(DISTINCT '+case.column(case.headers.index('Utilisateur'))+') FROM events').fetchone()[0]==import_rows
                assert case.db.execute('SELECT count(*) FROM events WHERE '+case.column(case.headers.index('PID'))+"='42'").fetchone()[0]==import_rows
            finally:case.close()
            assert sha256(source)==before
            report['persisted_collection']={'records':import_rows,'source_bytes':source.stat().st_size,
                                            'seconds':time.monotonic()-start,'peak_rss_bytes':peak[0],
                                            'source_sha256':before,'checks':['row count','distinct users','PID values','unchanged source']}
    finally:
        stop.set();watcher.join()
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--gib',type=float,default=32)
    parser.add_argument('--import-rows',type=int,default=200000)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    report=qualify(args.directory,args.gib,args.import_rows)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
