"""Parse every raw input with the qualified EXE engines and record diagnostics."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

from scripts.raw_pack.package import ROOT, GIB, digest
from scripts.test_pack.validate_windows import extract_engines
from scripts.test_pack.package import APP_COMMIT, APP_SHA256


def verify_inputs(root, manifest):
    for item in manifest['files']:
        path = root / item['path']
        if path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
            raise ValueError('Raw input differs from its manifest: ' + item['path'])


def validate(directory, executable, output):
    if sys.platform != 'win32':
        raise RuntimeError('Native Windows validation is required')
    from PySide6.QtWidgets import QApplication
    from fireblade.core.collection import Collection, ToolPack, PARSERS
    from fireblade.core.engine import Case
    from fireblade.core.models import View
    from fireblade.core.settings import Settings
    from fireblade.validation.forensic_tools import parser_result_display
    directory, output = Path(directory).resolve(), Path(output).resolve()
    root = directory / ROOT
    output.mkdir(parents=True, exist_ok=True)
    os.environ['LOCALAPPDATA'] = str(output / 'profile')
    manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
    verify_inputs(root, manifest)
    expected_linux = {item['path']: item for item in json.loads((root / 'SCENARIO-LINUX.json').read_text(encoding='utf-8'))['logs']}
    settings = Settings(memory_mb=512, threads=2)
    app = QApplication.instance() or QApplication([])
    report = dict(status='running', application_commit=APP_COMMIT, application_sha256=APP_SHA256,
                  raw_bytes=manifest['raw_bytes'], settings=dict(duckdb_memory_mb=512, threads=2, organization='files'),
                  automation='Native engines; outputs opened in DuckDB; first successful output per reader rendered by real Qt Windows source UI',
                  files=[], successful_readers={}, linux_rows=0, errors=[], warnings=[], unknown=[])
    report_path = output / 'validation-windows.json'
    def save():
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    save()
    try:
        pack = ToolPack(extract_engines(executable, output / 'engines'))
        entries = [dict(path=str(root / item['path']), sha256=item['sha256'])
                   for item in manifest['files']
                   if item['origin']['kind'] in ('public-native', 'synthetic-raw-linux')]
        for number, entry in enumerate(entries):
            relative = Path(entry['path']).relative_to(root).as_posix()
            tools = entry.get('tools', [])
            # scan() records recognized readers under parsers on some older sources.
            if not tools:
                from fireblade.core.collection import identify
                tools = identify(entry['path'])
            if tools == ['companion']:
                continue
            if not tools:
                report['unknown'].append(relative)
                continue
            source = Path(entry['path'])
            with tempfile.TemporaryDirectory(prefix='raw-parse-', dir=output) as scratch:
                # Feed an exact copy through Fireblade's ordinary Collection
                # parser. Keep the collector path and hive companions intact.
                copied = Path(scratch) / 'input' / relative
                copied.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, copied)
                for suffix in ('.LOG1', '.LOG2', '-wal', '-shm'):
                    companion = source.with_name(source.name + suffix)
                    if companion.is_file():
                        shutil.copyfile(companion, copied.with_name(copied.name + suffix))
                if digest(copied) != entry['sha256']:
                    raise AssertionError('Input copy mismatch: ' + relative)
                collection = Collection(copied.parent, Path(scratch) / 'analysis', pack, settings, organization='files')
                start = time.perf_counter()
                result = collection.parse()
                item = dict(path=relative, bytes=source.stat().st_size, tools=tools,
                            status=result['status'], seconds=round(time.perf_counter() - start, 3), runs=[])
                for file_entry in result['files']:
                    if file_entry.get('error'):
                        report['errors'].append(dict(path=relative, error=file_entry['error']))
                    for run in file_entry.get('runs', []):
                        rows = 0
                        for parsed in run.get('outputs', []):
                            case = Case(parsed['analysis'], settings=settings)
                            try:
                                count = case.count(View())
                                page = case.page(View())
                                rows += count
                            finally:
                                case.close()
                            if count and run['tool'] not in report['successful_readers']:
                                with parser_result_display(app, settings) as display:
                                    display(parsed['analysis'], page)
                                report['successful_readers'][run['tool']] = relative
                        observed = dict(tool=run['tool'], status=run['status'], rows=rows,
                                        warnings=run.get('warnings', []), error=run.get('error'))
                        item['runs'].append(observed)
                        if run['status'] == 'error':
                            report['errors'].append(dict(path=relative, tool=run['tool'], error=run.get('error')))
                        if run.get('warnings') or run['status'] in ('no_output', 'complete_with_warnings'):
                            report['warnings'].append(dict(path=relative, tool=run['tool'], status=run['status'], warnings=run.get('warnings', [])))
                        if relative in expected_linux and run['tool'] == 'CatScale':
                            if rows != expected_linux[relative]['lines']:
                                raise AssertionError(f'Linux row count mismatch: {relative}: {rows}')
                            report['linux_rows'] += rows
                report['files'].append(item)
                if digest(source) != entry['sha256']:
                    raise AssertionError('Raw source changed during parsing: ' + relative)
            if number % 20 == 0:
                print(f'Parsed raw input {number + 1}/{len(entries)}: {relative}', flush=True)
                save()
        missing = sorted((set(PARSERS) | {'Shellbags', 'WebCache', 'CatScale'}) - set(report['successful_readers']))
        if missing:
            raise AssertionError('No successful reference output for readers: ' + ', '.join(missing))
        report['native_bytes_with_rows'] = sum(item['bytes'] for item in report['files'] if item['path'].startswith('01-Windows/') and any(run['rows'] > 0 for run in item['runs']))
        if report['native_bytes_with_rows'] < GIB:
            raise AssertionError('Less than 1 GiB of native Windows inputs produced parsed rows')
        expected_rows = sum(item['lines'] for item in expected_linux.values())
        if report['linux_rows'] != expected_rows:
            raise AssertionError('Some synthetic raw Linux logs were not parsed')
        if any(error['path'].startswith('02-Linux-CatScale/') for error in report['errors']):
            raise AssertionError('Synthetic raw Linux exercise had a parser error')
        verify_inputs(root, manifest)
        report.update(status='completed_with_diagnostics' if report['errors'] else 'passed',
                      scope='All raw inputs inventoried; source hashes checked; all 13 reader references succeeded; all synthetic log row counts matched. Public native-reader errors and warnings are listed, not treated as successful parsing.',
                      parsed_input_files=len(report['files']), readers=sorted(report['successful_readers']),
                      run_statuses=dict(Counter(run['status'] for item in report['files'] for run in item['runs'])))
    except Exception as error:
        report.update(status='failed', error=str(error))
        raise
    finally:
        save()
    shutil.copyfile(report_path, root / 'validation-windows.json')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.directory, args.exe, args.out)
    print(json.dumps({key: value for key, value in result.items() if key != 'files'}, ensure_ascii=False)[:5000])


if __name__ == '__main__':
    main()
