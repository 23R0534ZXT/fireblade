"""Reproducible coverage and independently verified export benchmark."""
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import time

from fireblade.core.coverage import audit
from fireblade.core.engine import Case
from fireblade.core.models import AnalysisSnapshot,View
from fireblade.core.workspace_reader import WorkspaceReader


def main():
    with tempfile.TemporaryDirectory(prefix='fireblade-coverage-benchmark-') as folder:
        root=Path(folder);evidence=root/'evidence';evidence.mkdir();docs=[];files=[]
        dates=['2026-11-02T12:00:00Z','2026-11-02T12:00:00','invalid','']
        for number in range(2):
            source=evidence/f'events-{number}.csv'
            with source.open('w',newline='') as stream:
                writer=csv.writer(stream);writer.writerow(['Timestamp','User','Description','Empty'])
                for n in range(60000):writer.writerow([dates[n%4],'watch' if n%10==0 else 'ordinary',f'Event {n} · quoted, multiline\nvalue',''])
            case=Case(root/f'analysis-{number}.timeline');case.import_csv(source)
            doc=AnalysisSnapshot(str(case.path),case.info,View(search='watch'),b'');docs.append(doc);case.close()
            files.append(dict(path=str(source),size=doc.source_info['size'],sha256=doc.source_info['sha256'],status='complete',tools=['native'],runs=[dict(tool='native',status='complete',outputs=[dict(csv=str(source),analysis=doc.path)])]))
        inventory=dict(source=str(evidence),output=str(root/'collection'),status='complete',files=files,documents=[dict(path=d.path) for d in docs])
        started=time.monotonic();report=audit(WorkspaceReader(docs),collections=[inventory],verify_hashes=True);audit_seconds=time.monotonic()-started
        assert report['counts']['error']==0
        assert all((s['read'],s['selected'],s['dated'],s['undated'],s['naive'])==(60000,6000,30000,30000,15000) for s in report['sources'])
        assert all(s['empty_columns']==['Empty'] for s in report['sources'])
        case=Case(docs[0].path)
        try:
            started=time.monotonic();receipt=case.export(root/'export.csv',docs[0].view);export_seconds=time.monotonic()-started
        finally:case.close()
        assert receipt['verified_rows']==receipt['written']==receipt['expected']==6000
        assert all(hashlib.sha256(Path(d.source_info['path']).read_bytes()).hexdigest()==d.source_info['sha256'] for d in docs)
        print(json.dumps(dict(rows=120000,analyses=2,audit_seconds=round(audit_seconds,2),verified_export_rows=receipt['verified_rows'],export_seconds=round(export_seconds,2),errors=report['counts']['error'],warnings=report['counts']['warning'])))


if __name__=='__main__':main()
