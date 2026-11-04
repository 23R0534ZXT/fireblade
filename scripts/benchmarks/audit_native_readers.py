"""Exercise real managed parsers and Hayabusa from an extracted verified tool pack.

On Linux pass a compatible dotnet executable and the Linux Hayabusa binary of
the same version. This does not execute the Windows EXE or qualify Windows APIs.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

from fireblade.core.collection import Collection, PARSERS, ToolPack, execute
from fireblade.core.engine import Case
from fireblade.core.models import View


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class LocalPack(ToolPack):
    def __init__(self, root, dotnet, hayabusa):
        super().__init__(root)
        self.dotnet, self.hayabusa = dotnet, hayabusa

    def command(self, name):
        if name == 'Hayabusa': return [str(self.hayabusa)]
        return [str(self.dotnet), str(self.root/name/(name+'.dll'))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolpack', type=Path, required=True)
    parser.add_argument('--dotnet', type=Path, required=True)
    parser.add_argument('--hayabusa', type=Path, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args(); args.directory.mkdir(parents=True, exist_ok=False)
    report = dict(platform=os.name, scope='real managed parsers; native Hayabusa for host OS', help=[], parsers={})
    pack = LocalPack(args.toolpack.resolve(), args.dotnet.resolve(), args.hayabusa.resolve())
    def save():
        (args.directory/'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    for tool in (*PARSERS, 'Shellbags', 'Hayabusa'):
        started = time.monotonic()
        try:
            execute(pack.command(tool)+(['dfir-timeline', '--help'] if tool == 'Hayabusa' else ['--help']),
                    pack.root/tool, args.directory/(tool+'-help.log'), timeout=60)
            result = dict(tool=tool, status='passed')
        except Exception as error: result = dict(tool=tool, status='error', error=str(error))
        result['seconds'] = round(time.monotonic()-started, 3); report['help'].append(result); save()
    evidence = args.directory/'evidence'; evidence.mkdir()
    shutil.copy2(pack.root/'qa/System.evtx', evidence/'System.evtx')
    for compressed in (pack.root/'qa/registry').glob('*.gz'):
        with gzip.open(compressed, 'rb') as incoming, (evidence/compressed.stem).open('xb') as outgoing:
            shutil.copyfileobj(incoming, outgoing)
    shutil.copytree(pack.root/'qa/matrix', evidence/'matrix')
    shutil.copytree(pack.root/'qa/browser', evidence/'browser')
    before = {str(p.relative_to(evidence)): digest(p) for p in evidence.rglob('*') if p.is_file()}
    collection = Collection(evidence, args.directory/'collection', pack)
    report['collection'] = collection.parse()
    for entry in report['collection']['files']:
        for run in entry.get('runs', []):
            result = report['parsers'].setdefault(run['tool'], dict(runs=[], rows=0, outputs=0))
            details = dict(status=run['status'], source=entry['path'], error=run.get('error'), warnings=run.get('warnings', []))
            result['runs'].append(details)
            for output in run['outputs']:
                case = Case(output['analysis'])
                try:
                    count = case.count(View()); page = case.page(View())
                    assert not count or page
                    result['rows'] += count; result['outputs'] += 1
                finally: case.close()
    save()
    try:
        report['detection'] = collection.analyze()['detection']; save()
        if report['detection']['status'] in ('complete', 'complete_with_warnings'):
            from fireblade.core.alert_context import build_context
            case = Case(report['detection']['analysis'])
            try:
                row = case.page(View())[0]; alert = dict(zip(case.headers, row[1:]))
            finally: case.close()
            report['context'] = build_context(collection, alert, report['detection']['analysis'], row[0])
    except Exception as error: report['detection_error'] = str(error)
    report['source_unchanged'] = all(digest(evidence/name) == value for name, value in before.items())
    report['source_hashes'] = before
    report['unqualified_parsers'] = [tool for tool in PARSERS if not report['parsers'].get(tool, {}).get('rows') or
                                    any(run['status'] != 'complete' for run in report['parsers'][tool]['runs'])]
    save()
    print(json.dumps(dict(parsers=report['parsers'], unqualified=report['unqualified_parsers'],
                          detection=report.get('detection'), context=report.get('context'),
                          source_unchanged=report['source_unchanged']), ensure_ascii=False, indent=2))
    if report['unqualified_parsers'] or not report['source_unchanged']: raise SystemExit(1)


if __name__ == '__main__': main()
