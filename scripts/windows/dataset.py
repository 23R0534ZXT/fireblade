"""Deterministic, varied multi-GB CSV and an independent Python reference oracle."""
from collections import Counter
import csv
from datetime import datetime, timedelta
import hashlib
import io
import json
from pathlib import Path
import random
import time

HEADERS=['Timestamp','Artifact','EventID','User','Computer','PID','RecordID','ParentPath','FileName','Extension','Action','Size','SHA256','CommandLine','Description','Unicode','JSON','Empty']
ARTIFACTS=['MFT','EVTX','Prefetch','Amcache','LNK','JumpList','Registry','SRUM']
EXTENSIONS=['.exe','.dll','.ps1','.txt','.lnk','.dat']
COMBINATIONS=[[1],[3],[4],[2],[9],[1,3],[4,2],[2,3],[9,10],[3,1],[1,3,4]]
BASE=9007199254740993


def generate(directory,target_bytes=3*1024**3):
    directory=Path(directory)
    if directory.exists():raise ValueError('Dataset directory must be new')
    directory.mkdir(parents=True)
    source=directory/'artefacts variés 3GiB.csv'
    rng=random.Random(0xF1B1ADE)
    counters=[Counter() for _ in COMBINATIONS]
    reference=Counter();samples={};leading=[]
    digest=hashlib.sha256();index=0;last=None
    start=time.perf_counter()
    with source.open('wb') as output:
        header=io.StringIO(newline='');writer=csv.writer(header,lineterminator='\r\n');writer.writerow(HEADERS)
        data=b'\xef\xbb\xbf'+header.getvalue().encode('utf-8');output.write(data);digest.update(data)
        while output.tell()<target_bytes:
            block=io.StringIO(newline='');writer=csv.writer(block,lineterminator='\r\n')
            for _ in range(4096):
                i=index
                artifact=ARTIFACTS[i%8];user='' if i%101==0 else f'user{i%257:03d}'
                computer=f'WS-{(i//5)%64:03d}';event=str([4624,4625,4688,7045,1102,1,3,7,10,11,12,13][i%12])
                record='' if i%1999==0 else ('invalid-'+str(i) if i%991==0 else ('000' if i%17==0 else '')+str(BASE+i))
                second=i%172800
                stamp='' if i%1979==0 else ('bad-date' if i%733==0 else str(datetime(2026,10,30)+timedelta(seconds=second)))
                token=f'{rng.getrandbits(512):0128x}';payload=f'{rng.getrandbits(1024):0256x}'
                extension=EXTENSIONS[i%6];action='' if i%113==0 else ['Create','Read','Execute','Delete','Modify'][i%5]
                row=[stamp,artifact,event,user,computer,str((i*13)%65535),record,
                     'C:\\Evidence\\Utilisateur été\\'+token[:24],f'file-{i:09d}'+extension,extension,action,
                     str((i*7919)%10**10),token[:64],f'powershell.exe -File C:\\Scripts\\audit-{i}.ps1 -Argument "{payload}"',
                     f'Enregistrement {i}, "activité" {payload}'+ ('\nSeconde ligne : élève' if i%137==0 else ''),
                     f'élève-日本語-{i}',json.dumps(dict(record=i,token=token,payload=payload),ensure_ascii=False),'']
                writer.writerow(row)
                normalized=[value if value!='' else None for value in row]
                for cols,counter in zip(COMBINATIONS,counters):counter[tuple(normalized[c] for c in cols)]+=1
                reference['user042']+=user=='user042'
                reference['user042_MFT']+=user=='user042' and artifact=='MFT'
                reference['user042_or_user043']+=user in ('user042','user043')
                reference['user_regex']+=user!='' and 40<=i%257<=49
                reference['empty_user']+=user==''
                reference['date_after']+=stamp not in ('','bad-date') and second>=86400
                reference['invalid_ids']+=record.startswith('invalid-')
                reference['empty_ids']+=record==''
                if record.startswith('000') and len(leading)<1000:leading.append(record)
                if i in (0,1,137,990,1998):samples[str(i+1)]=normalized
                last=normalized;index+=1
            data=block.getvalue().encode('utf-8');output.write(data);digest.update(data)
            if index%131072==0:print(f'Dataset: {output.tell():,} bytes, {index:,} records',flush=True)
    samples[str(index)]=last
    def levels_for(cols,counter):
        path=[];levels=[]
        for depth in range(len(cols)):
            values=Counter()
            for key,count in counter.items():
                if list(key[:depth])==path:values[key[depth]]+=count
            ordered=sorted(values.items(),key=lambda pair:(-pair[1],pair[0] is None,'' if pair[0] is None else pair[0]))
            levels.append(dict(path=path.copy(),expected=ordered))
            path.append(ordered[0][0])
        return dict(columns=cols,levels=levels)
    scenarios=[levels_for(cols,counter) for cols,counter in zip(COMBINATIONS,counters)]
    filtered_counter=Counter({(key[0],key[2]):count for key,count in counters[-1].items() if key[1]=='user042'})
    filtered_groups=levels_for([1,4],filtered_counter)
    scenarios.append(dict(columns=[6],levels=[dict(path=[],expected=[(None,reference['empty_ids'])]+[(v,1) for v in sorted(leading)[:249]],partial=True)]))
    result=dict(format='fireblade-qa-dataset',source=str(source.resolve()),bytes=source.stat().st_size,rows=index,
                sha256=digest.hexdigest(),seed='0xF1B1ADE',headers=HEADERS,reference=reference,samples=samples,
                groups=scenarios,filtered_groups=filtered_groups,generation_seconds=round(time.perf_counter()-start,3),
                description='Synthetic varied UTF-8 BOM/CRLF, unique random payloads, multiline quotes, Unicode, NULLs and exact large IDs. Filesystem cache not purged.')
    (directory/'spec.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result
