"""Reproducible synthetic benchmark. Run in a fresh process (see README)."""
import argparse
import json
import platform
import sys
import threading
import time
from pathlib import Path

import duckdb
import psutil

from timeline_next.engine import Case, Filter, View


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--gib', type=float, default=1.05)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    source = args.directory / 'benchmark.csv'
    database = args.directory / 'benchmark.timeline'
    if source.exists() or database.exists():
        parser.error('Choose a new directory; existing data is never overwritten.')
    # Generation outside timed import. Realistic shape, deliberately repetitive data.
    block = b''.join(f'2026-01-01 12:00:00,{i % 12},user{i % 80},000{i},C:\\Windows\\System32\\file{i}.dll,{"artifact detail " * 20}\n'.encode() for i in range(10000))
    with source.open('wb') as f:
        f.write(b'Timestamp,EventID,User,RecordID,Path,Description\n')
        for _ in range(max(1, int(args.gib * 1024**3 / len(block)) + 1)):
            f.write(block)
    process = psutil.Process()
    peak = [0]
    stop = threading.Event()
    def monitor():
        while not stop.wait(.05):
            peak[0] = max(peak[0], process.memory_info().rss)
    thread = threading.Thread(target=monitor)
    thread.start()
    timings = {}
    def measure(name, fn):
        start = time.perf_counter()
        result = fn()
        timings[name] = round(time.perf_counter() - start, 3)
        return result
    c = Case(database, memory_mb=256)
    try:
        info = measure('import_with_two_sha256_passes_s', lambda: c.import_csv(source, progress=lambda s: print(s, flush=True)))
        measure('first_page_s', lambda: c.page(View()))
        measure('group_two_columns_s', lambda: c.page(View(groups=[1, 2])))
        measure('numeric_sort_first_page_s', lambda: c.page(View(sort_column=3, sort_type='number')))
        count = measure('filtered_count_s', lambda: c.count(View(filters=[Filter(1, 'eq', '1')])) )
    finally:
        c.close()
        stop.set()
        thread.join()
    result = dict(python=sys.version.split()[0], duckdb=duckdb.__version__,
                  platform=platform.platform(), cpu_count=psutil.cpu_count(),
                  csv_bytes=source.stat().st_size, rows=info['rows'],
                  database_bytes=database.stat().st_size, peak_process_rss_mib=round(peak[0] / 1024**2, 1),
                  duckdb_memory_limit_mib=256, threads=2, filtered_count=count, timings=timings,
                  caveat='Synthetic repetitive data; warm filesystem cache; not a comparison with Timeline Explorer.')
    (args.directory / 'results.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
