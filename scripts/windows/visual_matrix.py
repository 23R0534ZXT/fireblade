"""Windows light/dark preferences x four DPI scales; restore registry afterwards."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import winreg

from scripts.windows.qa_process import run_executable


def environment(base,scale,profile):
    env=os.environ.copy()
    for key in ('PYTHONPATH','PYTHONHOME','QT_PLUGIN_PATH','QT_QPA_PLATFORM_PLUGIN_PATH'):
        env.pop(key,None)
    system=Path(env.get('SystemRoot',r'C:\Windows'))
    env.update(QT_QPA_PLATFORM='windows',QT_SCALE_FACTOR=str(scale),PYTHONUTF8='1',PYTHONNOUSERSITE='1',
               LOCALAPPDATA=str(profile),PATH=os.pathsep.join(map(str,[system/'System32',system])))
    return env


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--exe',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();args.out=args.out.resolve();args.exe=args.exe.resolve();args.out.mkdir(parents=True,exist_ok=True)
    registry=r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize'
    key=winreg.CreateKey(winreg.HKEY_CURRENT_USER,registry);previous={}
    for name in ('AppsUseLightTheme','SystemUsesLightTheme'):
        try:previous[name]=winreg.QueryValueEx(key,name)
        except FileNotFoundError:previous[name]=None
    results=[]
    try:
        with tempfile.TemporaryDirectory(prefix='Fireblade visual ') as temp:
            root=Path(temp);binary=root/'Application été';binary.mkdir();exe=binary/'Fireblade.exe';shutil.copy2(args.exe,exe)
            for mode in ('light','dark'):
                for name in previous:winreg.SetValueEx(key,name,0,winreg.REG_DWORD,1 if mode=='light' else 0)
                for scale in (1,1.25,1.5,2):
                    folder=args.out/f'{mode}-{scale}';folder.mkdir()
                    report=folder/'report.json'
                    print(f'::notice title=Visual QA::{mode}, scale {scale}',flush=True)
                    code=run_executable([str(exe),'--appearance-report',str(report)],cwd=root,
                                             env=environment(root,scale,root/f'profile-{mode}-{scale}'),timeout=60)
                    result=json.loads(report.read_text(encoding='utf-8')) if report.exists() else dict(status='failed',error='No report')
                    result.update(windows_preference=mode,requested_scale=scale,exit_code=code)
                    results.append(result)
                    (args.out/'matrix.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    finally:
        for name,value in previous.items():
            if value is None:
                try:winreg.DeleteValue(key,name)
                except FileNotFoundError:pass
            else:winreg.SetValueEx(key,name,0,value[1],value[0])
        winreg.CloseKey(key)
    if any(r['status']!='passed' or r['exit_code'] for r in results):
        raise RuntimeError('Visual QA matrix failed; inspect every report and screenshot')


if __name__=='__main__':main()
