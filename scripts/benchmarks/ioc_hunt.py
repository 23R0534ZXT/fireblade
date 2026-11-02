import csv,tempfile,time,json,hashlib
from pathlib import Path
from fireblade.core.engine import Case
from fireblade.core.models import AnalysisSnapshot,View
from fireblade.core.ioc_hunt import parse_indicators
from fireblade.core.ioc_results import hunt
from fireblade.core.workspace_reader import WorkspaceReader
with tempfile.TemporaryDirectory() as folder:
    root=Path(folder);source=root/'evidence.csv'
    with source.open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['Timestamp','IP','Message'])
        for n in range(100000):writer.writerow(['2026-11-02T12:00:00Z',f'10.1.{(n%50000)//256}.{n%256}',f'Observed host{n%50000}.example.org'])
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    case=Case(root/'analysis.timeline');case.import_csv(source)
    document=AnalysisSnapshot(str(case.path),case.info,View(),b'');case.close()
    started=time.monotonic();batch=parse_indicators('\n'.join(f'host{n}.example.org' for n in range(50000)));parse_seconds=time.monotonic()-started
    started=time.monotonic();store=hunt(WorkspaceReader([document]),batch,root/'hunts',hit_limit=1000);seconds=time.monotonic()-started
    assert store.metadata['matching_fields']==100000 and store.metadata['matched_iocs']==50000
    assert all(row[5:7]==(2,2) for row in store.indicators())
    assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
    print(json.dumps(dict(rows=100000,iocs=50000,parse_seconds=round(parse_seconds,2),scan_seconds=round(seconds,2),matches=store.metadata['matching_fields'],stored=store.metadata['stored_hits'],source_sha256=digest)))
    store.close()
