"""Compare exact numeric sorting and paging on an existing imported case.

Runs sequentially in one process; later phases benefit from warm caches. This
checks identical returned values, not just speed. psutil is a dev dependency.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import threading
import time

import duckdb
import psutil

from timeline_next.engine import Case
from timeline_next.models import View
from timeline_next.settings import Settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--column", type=int, default=3)
    parser.add_argument("--offsets", nargs="+", type=int, default=[0, 250, 500, 1000, 1000000])
    args = parser.parse_args()
    if not args.case.is_file() or any(offset < 0 for offset in args.offsets):
        parser.error("Choose an existing analysis and nonnegative offsets")
    if args.output.resolve() == args.case.resolve():
        parser.error("The output cannot replace the case")
    process = psutil.Process()
    peak = [process.memory_info().rss]
    stop = threading.Event()
    def monitor():
        while not stop.wait(.01):
            peak[0] = max(peak[0], process.memory_info().rss)
    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    settings = Settings()
    case = None
    results, expected = {}, {}
    try:
        case = Case(args.case, settings=settings)
        if not case.info:
            parser.error("The analysis has no completed import")
        if args.output.resolve() == Path(case.info["path"]).resolve():
            parser.error("The output cannot replace the CSV source")
        column = case.column(args.column)
        view = View(sort_column=args.column, sort_type="number")
        for name in ("native_decimal", "integer_path_no_cache", "integer_path_with_cache"):
            results[name] = []
            for offset in args.offsets:
                print(f"{name} offset={offset}…", flush=True)
                start = time.perf_counter()
                if name == "native_decimal":
                    rows = case.db.execute(
                        f"SELECT * FROM events ORDER BY try_cast({column} AS DECIMAL(38,10)) ASC NULLS LAST, __row_id LIMIT ? OFFSET ?",
                        [settings.page_size, offset]).fetchall()
                elif name == "integer_path_no_cache":
                    rows = case.db.execute("SELECT * FROM events" + case.order(view) + " LIMIT ? OFFSET ?", [settings.page_size, offset]).fetchall()
                else:
                    rows = case.page(view, offset=offset)
                elapsed = time.perf_counter() - start
                digest = hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()
                if name == "native_decimal":
                    expected[offset] = digest
                elif expected[offset] != digest:
                    raise AssertionError(f"Different sorted values at offset {offset}")
                results[name].append(dict(offset=offset, seconds=round(elapsed, 4), rows=len(rows), sha256=digest))
                print(f"  {elapsed:.4f} s; {len(rows)} rows; identical values", flush=True)
        report = dict(python=sys.version.split()[0], duckdb=duckdb.__version__,
                      platform=platform.platform(), source_bytes=case.info["size"],
                      source_rows=case.info["rows"], memory_limit_mb=settings.memory_mb,
                      threads=settings.threads, timings=results,
                      peak_process_rss_mib=round(peak[0] / 1024**2, 1),
                      caveat="Synthetic/repetitive case; same process and sequential warm-cache phases; no Windows or real artefact measurements.")
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2), flush=True)
    finally:
        stop.set()
        monitor_thread.join()
        if case is not None:
            case.close()


if __name__ == "__main__":
    main()
