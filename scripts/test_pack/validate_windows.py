"""Validate the exact downloadable ZIP with the engines from the qualified EXE."""
import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import sys
import zipfile

from scripts.test_pack.package import APP_SHA256,ROOT,HEADERS,ROWS,digest,verify_archive


def extract_engines(executable,target):
    if digest(executable)!=APP_SHA256:raise ValueError('The test pack must use the qualified Fireblade.exe')
    from PyInstaller.archive.readers import CArchiveReader
    reader=CArchiveReader(str(executable));target=Path(target).resolve();target.mkdir(parents=True)
    prefix='resources/forensic-tools/'
    files=0
    for name,entry in reader.toc.items():
        normalized=name.replace('\\','/')
        if not normalized.startswith(prefix):continue
        relative=normalized[len(prefix):];path=(target/relative).resolve()
        if target not in path.parents:raise ValueError('Unsafe embedded resource path')
        if entry[-1]=='n':raise ValueError('Unexpected symbolic resource')
        data=reader.extract(name)
        if not isinstance(data,bytes):raise ValueError('Non-file embedded resource')
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);files+=1
    if not files or not (target/'dotnet/dotnet.exe').is_file():raise ValueError('Bundled engines not found')
    return target


def validate(archive,executable,directory):
    if sys.platform!='win32':raise RuntimeError('Native Windows validation required for SRUM and SQLite')
    from PySide6.QtWidgets import QApplication
    from fireblade.core.collection import Collection,ToolPack,PARSERS
    from fireblade.core.engine import Case
    from fireblade.core.models import View,Filter
    from fireblade.validation.forensic_tools import parser_result_display,verify_parser_results
    manifest=verify_archive(archive)
    directory=Path(directory).resolve();directory.mkdir(parents=True)
    evidence=directory/'unpacked'
    with zipfile.ZipFile(archive) as zipped:zipped.extractall(evidence)
    root=evidence/ROOT
    engines=extract_engines(executable,directory/'engines');pack=ToolPack(engines)
    os.environ['LOCALAPPDATA']=str(directory/'profile')
    app=QApplication.instance() or QApplication([])
    report=dict(status='running',platform=sys.platform,application_sha256=digest(executable),archive_sha256=digest(archive),cases=[])
    path=directory.parent/'validation-windows.json'
    def save():path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save()
    try:
        with parser_result_display(app) as display:
            def inspect(collection,label):
                collection.parse();total=0
                for document in collection.report['documents']:
                    case=Case(document['path'])
                    try:count=case.count(View());page=case.page(View());total+=count
                    finally:case.close()
                    display(document['path'],page)
                report['cases'].append(dict(name=label,analyses=len(collection.report['documents']),rows=total,status='passed'));save()
                return total
            main=Collection(root/'01-Windows/01-Collecte-principale',directory/'windows-main',pack)
            main.parse();report['parsers']=verify_parser_results(main.report,display)
            if set(report['parsers'])!=set(PARSERS):raise AssertionError('Missing main parser')
            main.analyze()
            if main.report['detection']['status']!='complete' or main.report['detection']['alerts']<2:raise AssertionError(str(main.report['detection']))
            report['hayabusa_alerts']=main.report['detection']['alerts'];save()
            for subdir,tool,expected in [('02-Shellbags','Shellbags',523),('03-WebCache','WebCache',1612)]:
                collection=Collection(root/'01-Windows'/subdir,directory/subdir,pack)
                total=inspect(collection,tool)
                actual=0
                for entry in collection.report['files']:
                    for run in entry.get('runs',[]):
                        if run['tool']!=tool:continue
                        if run['status'] not in ('complete','complete_with_warnings'):raise AssertionError(str(run))
                        for output in run['outputs']:
                            case=Case(output['analysis'])
                            try:actual+=case.count(View())
                            finally:case.close()
                if actual!=expected:raise AssertionError(f'{tool}: {actual} != {expected}')
            counts=[]
            for subdir in ('01-Dossier-extrait','02-Archive','03-Volume'):
                collection=Collection(root/'02-Linux-CatScale'/subdir,directory/subdir,pack,organization='artifacts')
                total=inspect(collection,subdir);counts.append(total)
                for entry in collection.report['files']:
                    for run in entry.get('runs',[]):
                        if run['status'] not in ('complete','complete_with_warnings'):raise AssertionError(str(run))
                if subdir!='03-Volume' and len(collection.report['documents'])!=7:raise AssertionError('Missing CatScale families')
            expected=manifest['expected']
            if counts!=[expected['catscale']['rows']]*2+[expected['volume_rows']]:raise AssertionError(str(counts))
            exports=[]
            for source in sorted((root/'03-Exports').iterdir()):
                case=Case(directory/(source.suffix[1:]+'.timeline'))
                try:
                    if source.suffix=='.xlsx':case.import_excel(source,'Activite')
                    else:case.import_csv(source,encoding='auto')
                    if case.count(View())!=6 or case.headers!=HEADERS:raise AssertionError('Export fixture changed')
                    if case.page(View())[0][-1]!='000001':raise AssertionError('Leading zeros lost')
                    if case.count(View(filters=[Filter(7,'eq','9007199254740993')]))!=1:raise AssertionError('Large ID lost')
                    page=case.page(View());exports.append(dict(format=source.suffix,rows=6))
                finally:case.close()
                display(case.path,page)
            report['exports']=exports
        report['status']='passed'
    except Exception as exc:
        report.update(status='failed',error=str(exc));raise
    finally:save()
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path,required=True);parser.add_argument('--exe',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(validate(args.archive,args.exe,args.out),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
