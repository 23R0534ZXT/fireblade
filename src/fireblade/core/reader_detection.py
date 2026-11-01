"""Bounded header matching against locally installed TLE readers.

Only the dedicated Readers directories and previously approved DLLs are inspected.
ExpectedHeaders contains alternative complete header records, not column subsets.
"""
import codecs
import csv
import io
from pathlib import Path
import sys

from fireblade.core import plugin_registry
from fireblade.core.errors import OperationCancelled, job_cancelled
from fireblade.runtime.windows_paths import user_directory


HEADER_LIMIT = 65536
MAX_HEADER_BYTES = 4 * 1024 * 1024


def reader_directories():
    directories = [user_directory() / 'Readers']
    if getattr(sys, 'frozen', False):
        directories.append(Path(sys.executable).parent / 'Readers')
    return directories


def check_cancelled():
    if job_cancelled():
        raise OperationCancelled()


def header_record(source):
    """Grow only while a header may be incomplete, never accept a prefix."""
    csv.field_size_limit(max(csv.field_size_limit(),MAX_HEADER_BYTES))
    data=bytearray();budget=min(HEADER_LIMIT,MAX_HEADER_BYTES);eof=False
    with Path(source).open('rb') as source_stream:
        while True:
            while len(data)<budget:
                check_cancelled()
                chunk=source_stream.read(min(HEADER_LIMIT,budget-len(data)))
                if not chunk:eof=True;break
                data.extend(chunk)
            if data.startswith((codecs.BOM_UTF32_LE,codecs.BOM_UTF32_BE)):encoding='utf-32'
            elif data.startswith((codecs.BOM_UTF16_LE,codecs.BOM_UTF16_BE)):encoding='utf-16'
            else:encoding='utf-8-sig'
            try:
                decoded=codecs.getincrementaldecoder(encoding)().decode(data,final=eof)
            except UnicodeError:
                if encoding!='utf-8-sig':return None
                decoded=data.decode('cp1252',errors='replace')
            from fireblade.core.csv_preamble import preamble_lines
            stream=io.StringIO(decoded,newline='');skip=preamble_lines(stream);stream.seek(0)
            for _ in range(skip):stream.readline()
            text=stream.read().lstrip('\r\n')
            incomplete=False
            for delimiter in (',','\t',';','|'):
                check_cancelled()
                candidate=io.StringIO(text,newline='')
                try:
                    next(csv.reader(candidate,delimiter=delimiter,strict=True))
                    if candidate.tell()>=len(text) and not text.endswith(('\n','\r')) and not eof:incomplete=True
                except StopIteration:
                    if not eof:incomplete=True
                except csv.Error as exc:
                    if 'unexpected end of data' in str(exc) and not eof:incomplete=True
            if not incomplete:return text
            if eof:return None
            if budget>=MAX_HEADER_BYTES:
                # A record ending exactly at the bound without a final newline
                # is complete only if the file really ends there.
                check_cancelled()
                if source_stream.read(1):return None
                eof=True
            else:budget=min(budget*2,MAX_HEADER_BYTES)


def signature(text, delimiter):
    try:
        stream = io.StringIO(text, newline='')
        row = next(csv.reader(stream, delimiter=delimiter, strict=True))
        return tuple(value.strip().casefold() for value in row) or None
    except (csv.Error, StopIteration):
        return None


def signatures(text):
    records = {delimiter: signature(text, delimiter) for delimiter in (',', '\t', ';', '|')}
    multiple = {delimiter: row for delimiter, row in records.items() if row and len(row) > 1}
    # Parsing a comma header as one tab-separated field must not create a match.
    return multiple or {',': records[',']}


def detect_reader(source):
    """Return (DLL, type) or None; an explicit source binding takes precedence."""
    bound = plugin_registry.reader_for_source(source)
    if bound:
        return bound
    if Path(source).suffix.lower() in ('.xls', '.xlsx'):
        return None
    entries = plugin_registry.read()
    paths = {Path(entry['path']).resolve(): entry for entry in entries}
    installed = set()
    for directory in reader_directories():
        if directory.is_dir():
            installed.update(path.resolve() for path in directory.iterdir()
                             if path.is_file() and path.suffix.lower() == '.dll')
    candidates = sorted(set(paths) | installed, key=lambda p: str(p).casefold())
    if len(candidates) > 256:
        raise ValueError('256 DLL de lecteurs au maximum')
    if not candidates:
        return None
    text = header_record(source)
    if not text:
        return None
    actual = signatures(text)
    matches = set()
    changed = False
    for path in candidates:
        check_cancelled()
        entry = paths.get(path)
        if not path.is_file():
            continue
        sha = plugin_registry.digest(path)
        if entry and entry['sha256'] != sha and path not in installed:
            raise ValueError('DLL enregistrée modifiée : ' + str(path))
        if entry is None:
            entry = dict(path=str(path), sha256=sha, analyses=[], readers=[])
            entries.append(entry)
        elif entry['sha256'] != sha:
            entry.update(sha256=sha, analyses=[], readers=[])
            entry.pop('reader_catalog', None)
        catalog = entry.get('reader_catalog')
        if catalog is None:
            from fireblade.core.tle_plugins import inspect_plugin
            try:
                catalog = inspect_plugin(path, check_cancelled)
            except ValueError as exc:
                # Native dependency DLLs cannot implement managed reader contracts.
                if path in installed and ('BadImageFormatException' in str(exc) or 'Bad IL format' in str(exc)):
                    catalog = []
                else:
                    raise
            if plugin_registry.digest(path) != sha:
                raise ValueError('DLL modifiée pendant son inspection : ' + str(path))
            entry['reader_catalog'] = catalog
            changed = True
        for reader in catalog:
            for expected in reader.get('headers') or []:
                expected_records = signatures(expected)
                for delimiter, record in actual.items():
                    if record is not None and expected_records.get(delimiter) == record:
                        matches.add((path, reader['type']))
    check_cancelled()
    if changed:
        plugin_registry.save(entries)
    if len(matches) > 1:
        names = ', '.join(f'{path.name}: {kind}' for path, kind in sorted(matches))
        raise ValueError('En-tête ambigu : plusieurs lecteurs TLE correspondent (' + names + '). Utilisez l’import explicite pour ce fichier.')
    return next(iter(matches)) if matches else None
