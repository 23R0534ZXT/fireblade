"""Run upstream reader tests, then import their generated inputs via Fireblade.

This qualifies declared headers with synthetic typed rows. It is deliberately
reported separately from real forensic export coverage.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

from scripts.windows.verify_upstream_plugin import REVISION, ARCHIVE_SHA256


def verify(host, output):
    from fireblade.core.engine import Case
    from fireblade.core.models import View
    from fireblade.core.tle_plugins import import_plugin
    output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    report=dict(status='running', platform=sys.platform, frozen=bool(getattr(sys,'frozen',False)), revision=REVISION, archive_sha256=ARCHIVE_SHA256,
                coverage='upstream synthetic typed inputs and supplied regression files; not all real exports', cases=[])
    path=output/'reader-matrix.json'
    def flush():path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    previous=os.environ.get('FIREBLADE_PLUGIN_HOST')
    os.environ['FIREBLADE_PLUGIN_HOST']=str(Path(host).resolve())
    try:
        with urllib.request.urlopen(f'https://codeload.github.com/EricZimmerman/TLEFilePlugins/zip/{REVISION}',timeout=60) as stream:
            data=stream.read(16*1024**2)
        if hashlib.sha256(data).hexdigest()!=ARCHIVE_SHA256:
            raise ValueError('Archive des lecteurs différente du SHA-256 épinglé')
        with tempfile.TemporaryDirectory(prefix='Fireblade reader matrix ') as temporary:
            root=Path(temporary)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:archive.extractall(root)
            upstream=next(root.glob('TLEFilePlugins-*'))
            project=upstream/'TLEFile.Test/TLEFile.Test.csproj'
            dotnet=os.environ.get('FIREBLADE_DOTNET','dotnet')
            tests=subprocess.run([dotnet,'test',str(project),'-c','Release','--logger','trx',
                                  '--results-directory',str(output/'upstream-tests')],cwd=upstream,check=False,timeout=600)
            results=list((output/'upstream-tests').glob('*.trx'))
            if not results:raise RuntimeError('Aucun rapport des tests amont')
            ns={'t':'http://microsoft.com/schemas/VisualStudio/TeamTest/2010'}
            counters=ET.parse(results[0]).getroot().find('.//t:Counters',ns)
            if counters is None:raise RuntimeError('Compteurs des tests amont absents')
            report['upstream_tests']=dict(counters.attrib)
            if tests.returncode or int(counters.get('passed','0'))<100 or int(counters.get('failed','0')):
                raise RuntimeError('Les tests amont ont échoué ou la matrice est incomplète')
            files=sorted(p for p in upstream.rglob('TLEFile*.csv') if re.fullmatch(r'TLEFile\w+\.[\w.]+_\d+',p.stem))
            if len(files)<100:raise RuntimeError('Moins de 100 variantes synthétiques produites par les lecteurs amont')
            binaries=project.parent/'bin/Release/net10.0'
            for index,source in enumerate(files):
                reader=source.stem.rsplit('_',1)[0]
                plugin=binaries/(reader.split('.')[0]+'.dll')
                item=dict(reader=reader, fixture=source.name, fixture_kind='upstream synthetic typed rows', status='failed')
                case=None
                try:
                    digest=hashlib.sha256(source.read_bytes()).hexdigest()
                    case=Case(root/f'analysis-{index}.timeline')
                    import_plugin(case,source,plugin,reader)
                    assert case.info['rows']==3
                    assert case.count(View())==3
                    line=case.headers.index('TLE_SourceLine')
                    assert [int(row[line+1]) for row in case.page(View())]==[1,2,3]
                    assert case.info['sha256']==digest==hashlib.sha256(source.read_bytes()).hexdigest()
                    item.update(status='passed',rows=3,columns=len(case.headers),source_sha256=digest)
                except Exception as error:
                    item['error']=str(error)
                finally:
                    if case is not None:case.close()
                report['cases'].append(item)
                flush()
            report['variants']=len(files)
            report['readers']=len({item['reader'] for item in report['cases']})
            if any(item['status']!='passed' for item in report['cases']):
                raise RuntimeError('Au moins un lecteur a échoué dans le pont Fireblade')
            report['status']='passed'
    except BaseException as error:
        report.update(status='failed',error=str(error))
        raise
    finally:
        flush()
        if previous is None:os.environ.pop('FIREBLADE_PLUGIN_HOST',None)
        else:os.environ['FIREBLADE_PLUGIN_HOST']=previous


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--host',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    verify(args.host,args.out)


if __name__=='__main__':main()
