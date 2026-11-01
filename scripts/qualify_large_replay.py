"""Opt-in >14-GiB engine qualification by replaying the existing verified CSV.

Never invokes the dataset generator. This is an engine workload, not a native
Windows GUI test or a performance comparison with Timeline Explorer.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import time

from scripts.windows.existing_dataset import prepare


REPEATS=5


def replay(source, target, expected_hash, repeats=REPEATS):
    """One header, repeated original CSV record bytes, bounded copy buffers."""
    source,target=Path(source),Path(target)
    if target.exists():raise FileExistsError(target)
    with source.open('rb') as stream:
        header=stream.readline(65537)
        if len(header)>65536 or not header.endswith(b'\n'):raise ValueError('Unexpected fixture header')
        body_offset=len(header)
    original=source.stat().st_size
    required=original*repeats-body_offset*(repeats-1)
    if shutil.disk_usage(target.parent).free<required*2+8*1024**3:
        raise RuntimeError('Replay plus database/spill requires more free disk space')
    hash_input=hashlib.sha256();hash_output=hashlib.sha256()
    try:
        with target.open('xb') as output:
            for iteration in range(repeats):
                with source.open('rb') as incoming:
                    if iteration:incoming.seek(body_offset)
                    while data:=incoming.read(4*1024**2):
                        output.write(data);hash_output.update(data)
                        if not iteration:hash_input.update(data)
        if hash_input.hexdigest()!=expected_hash:raise ValueError('Published source SHA-256 mismatch')
        assert target.stat().st_size==required
        return dict(bytes=required,sha256=hash_output.hexdigest(),repeats=repeats,header_bytes=body_offset,
                    construction='one original header plus repeated original record bytes; no regenerated base CSV')
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def qualify(directory, report_path, archive=None):
    from fireblade.core.engine import Case
    from fireblade.core.models import Filter,View
    from fireblade.core.settings import Settings
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=True)
    report_path=Path(report_path).resolve();report_path.parent.mkdir(parents=True,exist_ok=True)
    if report_path.exists():raise FileExistsError(report_path)
    report=dict(status='running',kind='large-replayed-csv-engine',platform=sys.platform,
                operating_system=platform.platform(),frozen=False,native_windows_gui=False,
                comparison_with_tle=False,checks=[])
    def flush():report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    def check(name,operation):
        started=time.perf_counter()
        value=operation()
        report['checks'].append(dict(name=name,status='passed',seconds=round(time.perf_counter()-started,3),details=value))
        flush()
    case=None
    try:
        spec=prepare(directory,archive=archive)
        source=Path(spec['source']);target=directory/'replayed-15GiB.csv'
        report['base']=dict(bytes=spec['bytes'],rows=spec['rows'],sha256=spec['sha256'],regenerated=False)
        def build():
            result=replay(source,target,spec['sha256'])
            assert result['bytes']>14*1024**3
            report['dataset']=result
            return result
        check('replay_verified_existing_records_above_14_gib',build)
        settings=Settings(memory_mb=256,threads=2)
        report['settings']=dict(memory_mb=settings.memory_mb,threads=settings.threads,max_loaded_rows=settings.max_loaded_rows)
        case=Case(directory/'replayed.timeline',settings=settings)
        def ingest():
            case.import_csv(target)
            assert case.info['sha256']==report['dataset']['sha256']
            assert case.info['rows']==REPEATS*spec['rows']
            return dict(rows=case.info['rows'],sha256=case.info['sha256'])
        check('import_all_records_under_256_mib_duckdb_limit',ingest)
        def samples():
            first=case.page(View(),offset=0)[0]
            last=case.page(View(),offset=case.info['rows']-1)[0]
            assert list(first[1:])==spec['samples']['1']
            assert list(last[1:])==spec['samples'][str(spec['rows'])]
            assert last[0]==REPEATS*spec['rows']
            return dict(first_row=first[0],last_row=last[0],source_precision_and_unicode=True)
        check('first_and_deep_last_source_records',samples)
        def filters():
            expected=REPEATS*spec['reference']['user042']
            view=View(filters=[Filter(3,'eq','user042')])
            assert case.count(view)==expected
            assert len(case.page(view))<=settings.page_size
            return dict(matches=expected,loaded_page_limit=settings.page_size)
        check('exact_filter_over_all_replayed_records',filters)
        def groups():
            rows=case.page(View(groups=[1]))
            expected={item[0]:item[1]*REPEATS for item in spec['groups'][0]['levels'][0]['expected']}
            assert {row[0]:row[1] for row in rows}==expected
            return dict(groups=len(rows),source_rows=sum(row[1] for row in rows))
        check('group_counts_over_all_replayed_records',groups)
        def reopen():
            nonlocal case
            case.close();case=Case(directory/'replayed.timeline',settings=settings)
            assert case.count(View())==REPEATS*spec['rows']
            return dict(rows=case.count(View()))
        check('close_and_reopen_persisted_analysis',reopen)
        report['status']='passed'
    except BaseException as error:
        report.update(status='failed',error=str(error))
        raise
    finally:
        if case is not None:case.close()
        flush()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--archive',type=Path)
    args=parser.parse_args()
    qualify(args.directory,args.report,args.archive)


if __name__=='__main__':main()
