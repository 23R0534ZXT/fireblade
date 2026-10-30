"""Verify interruption of the native import of an existing CSV, then reuse its DB.

Creates only a new work directory. The CSV is read and hashed, never rewritten.
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

from fireblade.core.engine import Case
from fireblade.core.errors import OperationCancelled
from fireblade.core.models import View


def digest(path):
    with path.open("rb") as incoming:
        return hashlib.file_digest(incoming, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--min-progress", type=float, default=10,
                        help="Wait for this native progress percentage before cancelling")
    args = parser.parse_args()
    if not args.source.is_file() or args.directory.exists() or not 0 < args.min_progress < 100:
        parser.error("Choose an existing CSV source and a new work directory")
    args.directory.mkdir(parents=True)
    before = digest(args.source)
    case = Case(args.directory / "interrupted.timeline")
    case.db.execute("SET enable_progress_bar=true")
    case.db.execute("SET enable_progress_bar_print=false")
    writing, failures, phases = threading.Event(), [], []
    def progress(message):
        print(message, flush=True)
        phases.append(message)
        if message == "Écriture des enregistrements sur disque…":
            writing.set()
    def work():
        try:
            case.import_csv(args.source, progress=progress)
        except Exception as exc:
            failures.append(exc)
    thread = threading.Thread(target=work, daemon=True)
    try:
        thread.start()
        if not writing.wait(60):
            raise TimeoutError("The import did not reach its CSV write phase")
        deadline = time.monotonic() + 10
        active_progress = -1
        while thread.is_alive() and time.monotonic() < deadline:
            active_progress = case.db.query_progress()
            if active_progress >= args.min_progress:
                break
            time.sleep(.001)
        if active_progress < args.min_progress or not thread.is_alive():
            raise RuntimeError("The native CSV query did not reach the requested progress while active")
        started = time.perf_counter()
        case.interrupt()
        thread.join(15)
        elapsed = time.perf_counter() - started
        if thread.is_alive():
            raise TimeoutError("Import did not stop within 15 seconds")
        if not (len(failures) == 1 and isinstance(failures[0], OperationCancelled)
                and isinstance(failures[0].__cause__, duckdb.InterruptException)):
            raise AssertionError(f"Unexpected import outcome: {failures}")
        remaining = case.db.execute("SHOW TABLES").fetchall()
        if remaining or case.headers or case.info:
            raise AssertionError("Partial imported tables or metadata remain")
        retry = args.directory / "retry.csv"
        retry.write_text("ID,User\n001,alice\n002,bob\n", encoding="utf-8")
        case.import_csv(retry)
        rows = case.page(View())
        if rows != [(1, "001", "alice"), (2, "002", "bob")]:
            raise AssertionError("The same database could not be reused correctly")
        after = digest(args.source)
        if after != before:
            raise AssertionError("The CSV source hash changed")
        report = dict(python=sys.version.split()[0], duckdb=duckdb.__version__,
                      platform=platform.platform(), source_bytes=args.source.stat().st_size,
                      source_sha256=before, source_unchanged=True,
                      phase_messages=phases, native_progress_at_cancel=active_progress,
                      requested_progress_percent=args.min_progress,
                      native_exception=type(failures[0].__cause__).__name__,
                      seconds_to_stop_and_rollback=round(elapsed, 4),
                      tables_after_cancel=remaining, retry_rows=len(rows),
                      caveat="Existing synthetic CSV, Linux, one cancellation during native import. No Windows or crash/power-loss test.")
        (args.directory / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2), flush=True)
    finally:
        if thread.is_alive():
            case.interrupt()
            thread.join(15)
        if not thread.is_alive():
            case.close()


if __name__ == "__main__":
    main()
