"""Generate >=3 GiB, then exercise the actual standalone Windows EXE."""
import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

from scripts.windows.dataset import generate
from scripts.windows.qa_process import run_executable


def main():
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['generate','run'])
    parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--exe',type=Path);parser.add_argument('--gib',type=float,default=3)
    args=parser.parse_args();args.out=args.out.resolve();args.directory=args.directory.resolve();args.out.mkdir(parents=True,exist_ok=True)
    if args.operation=='generate':
        if args.gib<3:parser.error('Qualification requires at least 3 GiB')
        if shutil.disk_usage(args.directory.parent).free<12*1024**3:raise RuntimeError('At least 12 GiB free disk space is required')
        spec=generate(args.directory,int(args.gib*1024**3))
        summary={k:v for k,v in spec.items() if k not in ('groups','samples')}
        (args.out/'dataset.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        return
    spec=args.directory/'spec.json'
    data=json.loads(spec.read_text(encoding='utf-8'))
    if data['bytes']<3*1024**3:raise RuntimeError('Input must exceed 3 GiB')
    source=Path(data['source']);source.chmod(stat.S_IREAD)
    try:
        with tempfile.TemporaryDirectory(prefix='Fireblade qualification ') as temp:
            root=Path(temp);binary=root/'Application été';binary.mkdir();exe=binary/'Fireblade.exe';shutil.copy2(args.exe,exe)
            env=os.environ.copy()
            for key in ('PYTHONPATH','PYTHONHOME','QT_PLUGIN_PATH','QT_QPA_PLATFORM_PLUGIN_PATH'):env.pop(key,None)
            system=Path(env.get('SystemRoot',r'C:\Windows'))
            env.update(QT_QPA_PLATFORM='windows',PYTHONUTF8='1',PYTHONNOUSERSITE='1',
                       LOCALAPPDATA=str(root/'Profil utilisateur'),PATH=os.pathsep.join(map(str,[system/'System32',system])))
            report=args.out/'stress.json'
            code=run_executable([str(exe),'--stress-spec',str(spec),'--stress-report',str(report)],cwd=root,env=env,timeout=2700)
            result=json.loads(report.read_text(encoding='utf-8')) if report.exists() else dict(status='failed',error='No report')
            print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
            if code or result['status']!='passed':raise RuntimeError('3-GiB GUI qualification failed')
    finally:source.chmod(stat.S_IREAD|stat.S_IWRITE)


if __name__=='__main__':main()
