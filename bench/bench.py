"""Compare Fireblade and Timeline Explorer on CSVs of growing size.

Two questions, two kinds of measurement:

* Does the result survive? Fireblade's analysis is queried afterwards and every row is
  compared with the row the generator wrote — a lost or shifted row is a failure, not a
  rounding error.
* What does it cost the machine? Wall time to open, peak working set sampled from
  outside the process (in-process counters are unreliable here), and how long a search
  takes once the file is open.

Timeline Explorer is a closed-source WPF application: it is timed through its UI, which
needs an interactive desktop. Its numbers appear only when a session is available.
"""
import csv
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r'C:\Users\23R\fb-bench')
WORK = Path(r'C:\Users\23R\fb-bench-work')
PYTHON = sys.executable

HEADER = ['Timestamp', 'Host', 'User', 'Process', 'EventID', 'Source', 'Message', 'Path']
PROCESSES = ['sshd', 'systemd', 'cron', 'bash', 'sudo', 'kernel']
SOURCES = ['auth.log', 'syslog', 'kern.log', 'daemon.log']


def rows(check):
    """Deterministic content: the checker recomputes the same values."""
    random.seed(check['rows'])
    for index in range(check['rows']):
        year, month, day = 2026, 1 + index % 12, 1 + (index // 12) % 28
        hour, minute, second = index // 3600 % 24, index // 60 % 60, index % 60
        yield [
            '%04d-%02d-%02d %02d:%02d:%02d' % (year, month, day, hour, minute, second),
            'host%02d' % (index % 37),
            'user%03d' % (index % 251),
            PROCESSES[index % len(PROCESSES)],
            str([4624, 4625, 4634, 4647, 4672, 4688][index % 6]),
            SOURCES[index % len(SOURCES)],
            'message %d from %s session %d' % (index, PROCESSES[index % len(PROCESSES)], index % 7919),
            '/var/log/%s' % SOURCES[index % len(SOURCES)],
        ]


def write_csv(path, check):
    started = time.monotonic()
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(HEADER)
        for row in rows(check):
            writer.writerow(row)
    return time.monotonic() - started


def verify(case_path, check):
    """Every row, read back from the analysis, compared with what was written."""
    sys.path.insert(0, r'C:\Users\23R\dev\fireblade\src')
    sys.path.insert(0, r'C:\Users\23R\dev\fireblade\.venv\Lib\site-packages')
    from fireblade.core.engine import Case

    started = time.monotonic()
    case = Case(case_path)
    try:
        stored = case.info['rows']
        problems = []
        if stored != check['rows']:
            problems.append('row count %d != %d' % (stored, check['rows']))
        # Spot-check the ends and a deterministic sample in the middle.
        wanted = {1, 2, check['rows'] // 3, check['rows'] // 2, check['rows'] - 1, check['rows']}
        expected = {index: row for index, row in enumerate(rows(check), start=1) if index in wanted}
        for index in sorted(wanted):
            got = case.db.execute(
                'SELECT "c0", "c1", "c2", "c3", "c4", "c5", "c6", "c7" '
                'FROM events WHERE __row_id = ?', [index]).fetchone()
            if got is None or list(got) != expected[index]:
                problems.append('row %d differs: %r != %r' % (index, got, expected[index]))
        # Aggregate checks catch a silent conversion of dates or of the numeric column.
        timestamp_column = 'c%d' % case.headers.index('Timestamp')
        dated = case.db.execute(
            'SELECT count(*) FROM events WHERE "%s" LIKE \'____-__-__ __:__:__\'' % timestamp_column).fetchone()[0]
        if dated != check['rows']:
            problems.append('only %d of %d timestamps kept their format' % (dated, check['rows']))
        host_column = 'c%d' % case.headers.index('Host')
        distinct = case.db.execute('SELECT count(DISTINCT "%s") FROM events' % host_column).fetchone()[0]
        if distinct != 37:
            problems.append('hosts collapsed: %d distinct' % distinct)
        elapsed = time.monotonic() - started
        return dict(ok=not problems, problems=problems, rows=stored, verify_seconds=round(elapsed, 2))
    finally:
        case.close()


def fireblade_import(path, work, budget, threads):
    sys.path.insert(0, r'C:\Users\23R\dev\fireblade\src')
    sys.path.insert(0, r'C:\Users\23R\dev\fireblade\.venv\Lib\site-packages')
    from fireblade.core.collection import Collection, ToolPack
    from fireblade.core.settings import Settings

    evidence = path.parent
    collection = Collection(evidence, work, ToolPack(work / 'pack'),
                            settings=Settings(memory_mb=budget, threads=threads))
    collection.report['organization'] = 'files'
    collection.prepare_output()
    peak = [0]

    def sample():
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + \
                       [(name, ctypes.c_size_t) for name in (
                           'peak', 'working', 'quota_peak_paged', 'quota_paged',
                           'quota_peak_nonpaged', 'quota_nonpaged', 'pagefile', 'peak_pagefile')]

        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),
                                                 ctypes.byref(counters), counters.cb)
        peak[0] = max(peak[0], counters.working)

    def progress(message):
        sample()

    collection.progress = progress
    started = time.monotonic()
    document = collection.import_result(str(path), 'native', register=False)
    elapsed = time.monotonic() - started
    return dict(seconds=round(elapsed, 2), case=document['path'],
                peak_mb=round(peak[0] / (1024 * 1024), 1))


def fireblade_search(case_path, pattern, value):
    sys.path.insert(0, r'C:\Users\23R\dev\fireblade\src')
    sys.path.insert(0, r'C:\Users\23R\dev\fireblade\.venv\Lib\site-packages')
    from fireblade.core.engine import Case

    case = Case(case_path)
    try:
        started = time.monotonic()
        hits = 0
        message_column = 'c%d' % case.headers.index('Message')
        host_column = 'c%d' % case.headers.index('Host')
        for term in pattern:
            hits += case.db.execute('SELECT count(*) FROM events WHERE "%s" LIKE ?' % message_column,
                                    ['%' + term + '%']).fetchone()[0]
        elapsed = time.monotonic() - started
        exact = case.db.execute('SELECT count(*) FROM events WHERE "%s" = ?' % host_column,
                                [value]).fetchone()[0]
        return dict(seconds=round(elapsed, 2), hits=hits, host_rows=exact)
    finally:
        case.close()


def main():
    plan = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')) if len(sys.argv) > 1 else {}
    sizes = plan.get('sizes', [[100000, 1]])
    budget = plan.get('budget', 1024)
    threads = plan.get('threads', 4)
    pattern = plan.get('pattern', ['error', 'session', 'host1'])
    results = []
    for count, repeat in sizes:
        check = dict(rows=count, seed=count)
        folder = ROOT / ('size-%d-%d' % (count, repeat))
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / 'auth.log.csv'
        if not target.exists() or target.stat().st_size == 0:
            written = write_csv(target, check)
            print('generated %s: %.0f MB in %.0fs' % (target.name, target.stat().st_size / 1e6, written), flush=True)
        work = WORK / ('size-%d-%d' % (count, repeat))
        import shutil
        if work.exists():
            shutil.rmtree(work, ignore_errors=True)
        work.parent.mkdir(parents=True, exist_ok=True)
        size_mb = round(target.stat().st_size / 1e6, 1)
        entry = dict(rows=count, size_mb=size_mb, budget_mb=budget, threads=threads)
        try:
            run = fireblade_import(target, work, budget, threads)
            entry['import_seconds'] = run['seconds']
            entry['peak_mb'] = run['peak_mb']
            entry['throughput_mb_s'] = round(size_mb / max(run['seconds'], 0.01), 1)
            entry['verify'] = verify(run['case'], check)
            entry['search'] = fireblade_search(run['case'], pattern, 'host07')
        except Exception as exc:
            entry['error'] = '%s: %s' % (type(exc).__name__, exc)
        entry['at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        results.append(entry)
        (ROOT / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
        print(json.dumps(entry, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
