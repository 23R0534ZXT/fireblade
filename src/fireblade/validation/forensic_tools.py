"""Run the actual embedded engines from the relocated one-file Windows EXE."""
import gzip
import shutil
import json
from pathlib import Path

from fireblade.core.collection import Collection, PARSERS, ToolPack, execute
from fireblade.runtime.resources import resource_path


def verify_embedded_engines(directory):
    directory=Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    pack=ToolPack(resource_path('forensic-tools'))
    manifest=json.loads((pack.root/'manifest.json').read_text(encoding='utf-8'))
    if {tool['name'] for tool in manifest['parsers']} != set(PARSERS):
        raise AssertionError('Pack de parseurs incomplet')
    for tool in PARSERS:
        execute(pack.command(tool)+['--help'],pack.root/tool,directory/(tool+'-help.log'),timeout=60)
    execute(pack.command('Hayabusa')+['dfir-timeline','--help'],pack.root/'Hayabusa',directory/'Hayabusa-help.log',timeout=60)
    source=pack.root/'qa'/'System.evtx'
    if not source.is_file():raise AssertionError('EVTX de qualification absent')
    evidence=directory/'evidence'
    evidence.mkdir()
    shutil.copy2(source,evidence/'System.evtx')
    for compressed in (pack.root/'qa'/'registry').glob('*.gz'):
        with gzip.open(compressed,'rb') as incoming,(evidence/compressed.stem).open('wb') as outgoing:
            shutil.copyfileobj(incoming,outgoing)
    collection=Collection(evidence,directory/'forensic-collection',pack)
    report=collection.parse()
    event=next(entry for entry in report['files'] if Path(entry['path']).name=='System.evtx')
    if event['status']!='complete':raise AssertionError(str(event))
    system=next(entry for entry in report['files'] if Path(entry['path']).name=='SYSTEM')
    if system['status']!='complete':raise AssertionError(str(system))
    report=collection.analyze()
    if report['detection']['status']!='complete' or report['detection']['alerts']<2:
        raise AssertionError(str(report['detection']))
    return dict(parsers=len(PARSERS),registry_plugins=len(manifest['registry_plugins']['included']),registry_fixture_passed=True,alerts=report['detection']['alerts'])
