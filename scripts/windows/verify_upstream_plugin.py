"""Build and run the real public TLE GenericCsv reader at a pinned revision."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request
import zipfile

REVISION='7199c81ba45a97be74b4e05da43cbaabecccf5ca'
ARCHIVE_SHA256='4ef5612909efd622175e0d63e72018918a4712bf25ec11890646ff47b0676aa1'


def verify(host,report):
    from fireblade.core.engine import Case
    from fireblade.core.models import View
    from fireblade.core.tle_plugins import inspect_plugin,import_plugin
    dotnet=os.environ.get('FIREBLADE_DOTNET','dotnet')
    with urllib.request.urlopen(f'https://codeload.github.com/EricZimmerman/TLEFilePlugins/zip/{REVISION}',timeout=60) as stream:data=stream.read(16*1024**2)
    if hashlib.sha256(data).hexdigest()!=ARCHIVE_SHA256:raise ValueError('Archive amont différente du SHA-256 épinglé')
    previous=os.environ.get('FIREBLADE_PLUGIN_HOST');os.environ['FIREBLADE_PLUGIN_HOST']=str(Path(host).resolve())
    try:
        with tempfile.TemporaryDirectory(prefix='Fireblade upstream ') as folder:
            root=Path(folder)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:archive.extractall(root/'source')
            project=next((root/'source').glob('*/TLEFileGenericCsv/TLEFileGenericCsv.csproj'))
            output=root/'compiled'
            subprocess.run([dotnet,'build',str(project),'-c','Release','-p:CopyLocalLockFileAssemblies=true','-o',str(output)],check=True,timeout=240)
            plugin=output/'TLEFileGenericCsv.dll';readers=inspect_plugin(plugin)
            reader=next(r for r in readers if 'Generic' in r['type'])
            source=root/'évidence.csv';source.write_text('User,ID\nalice,0001\névidence,9007199254740993\n',encoding='utf-8',newline='')
            digest=hashlib.sha256(source.read_bytes()).hexdigest();case=Case(root/'s.timeline')
            try:
                import_plugin(case,source,plugin,reader['type']);rows=case.page(View())
                assert rows[0][1:3]==('alice','0001') and rows[1][1:3]==('évidence','9007199254740993')
                assert case.info['sha256']==digest and hashlib.sha256(source.read_bytes()).hexdigest()==digest
            finally:case.close()
        report=Path(report);report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(json.dumps(dict(status='passed',repository='EricZimmerman/TLEFilePlugins',revision=REVISION,archive_sha256=ARCHIVE_SHA256,reader=reader,checks=['real upstream DLL','Unicode','leading zeros','large identifier','source provenance']),indent=2),encoding='utf-8')
    finally:
        if previous is None:os.environ.pop('FIREBLADE_PLUGIN_HOST',None)
        else:os.environ['FIREBLADE_PLUGIN_HOST']=previous


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--host',required=True);parser.add_argument('--out',required=True);args=parser.parse_args();verify(args.host,args.out)
