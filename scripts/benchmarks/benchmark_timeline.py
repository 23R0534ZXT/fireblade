"""Independent synthetic oracle for timeline indexing, deep pages and entities."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import threading
import time

import psutil

from fireblade.core.engine import Case
from fireblade.core.models import AnalysisSnapshot, View
from fireblade.core.timeline import TimelineStore
from fireblade.core.workspace_reader import WorkspaceReader


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--rows',type=int,default=250000)
    args=parser.parse_args()
    if not 250<=args.rows<=10000000:parser.error('Choose between 250 and 10000000 records')
    args.directory.mkdir(parents=True,exist_ok=False)
    source=args.directory/'events.csv';origin=datetime(2026,1,1,tzinfo=timezone.utc)
    with source.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['Timestamp','User','SourceIP','Path','SHA256','Description','ID'])
        for n in range(args.rows):
            timestamp=(origin+timedelta(seconds=n)).strftime('%Y-%m-%dT%H:%M:%S')+f'.{n%1000:09d}Z'
            writer.writerow([timestamp,f'user{n%101:04}',f'10.0.0.{n%51}',f'C:/Evidence/file-{n%31}',f'{n%7:064x}',
                             'Événement synthétique — valeur exacte',f'0009007199254740993{n}'])
    before=hashlib.file_digest(source.open('rb'),'sha256').hexdigest()
    process=psutil.Process();peak=[process.memory_info().rss];stop=threading.Event()
    def watch():
        while not stop.wait(.025):peak[0]=max(peak[0],process.memory_info().rss)
    monitor=threading.Thread(target=watch);monitor.start()
    case=Case(args.directory/'events.timeline',memory_mb=64)
    store=TimelineStore(memory_mb=64);timings={}
    def measure(name,fn):
        start=time.perf_counter();result=fn();timings[name]=round(time.perf_counter()-start,3);return result
    try:
        info=measure('source_import_s',lambda:case.import_csv(source))
        document=AnalysisSnapshot(str(case.path),info,View(),b'')
        reader=WorkspaceReader([document],active=case)
        measure('index_s',lambda:store.build(reader,{document.path:0}))
        result=measure('entity_query_s',lambda:store.page(text='user0042',kind='user',exact=True))
        expected=(args.rows-1-42)//101+1
        assert result['count']==expected
        last=measure('last_page_s',lambda:store.page(offset=args.rows-250))
        assert [r[1] for r in last['rows']]==list(range(args.rows-249,args.rows+1))
        extent=store.extent();histogram=measure('histogram_s',lambda:store.histogram(extent[0],extent[1]))
        assert sum(r[2] for r in histogram['rows'])==args.rows
        exported=measure('filtered_export_s',lambda:store.export_csv(args.directory/'matches.csv',text='user0042',kind='user',exact=True))
        assert exported==expected
        with (args.directory/'matches.csv').open(encoding='utf-8-sig',newline='') as stream:
            rows=csv.reader(stream);next(rows)
            for n,row in enumerate(rows):assert int(row[3])==43+n*101 and 'user0042' in row[5]
        assert hashlib.file_digest(source.open('rb'),'sha256').hexdigest()==before
        report=dict(status='passed',rows=args.rows,source_bytes=source.stat().st_size,source_sha256=before,
                    memory_limit_mb_per_database=64,peak_process_rss_mib=round(peak[0]/1024**2,1),
                    entity_matches=expected,timings=timings,
                    checks=['source_integrity','full_count','last_page_independent_oracle','entity_count_independent_oracle','histogram_count','every_filtered_export_row_id'],
                    caveat='Synthetic repeated entities; Linux source engine. Memory budgets are per DuckDB database, not total process RSS.')
        (args.directory/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))
    finally:store.close();case.close();stop.set();monitor.join()


if __name__=='__main__':main()
