"""Entry point that can diagnose startup failures of a console-less Windows EXE.

Only standard-library imports here: a missing Qt/DuckDB DLL must also be reported.
"""
from datetime import datetime, timezone
import faulthandler
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback

from fireblade.runtime.windows_paths import logs_directory


def report_argument(arguments):
    flags = ("--self-test-report", "--appearance-report", "--stress-report")
    for index, argument in enumerate(arguments):
        if argument in flags and index + 1 < len(arguments):
            return Path(arguments[index + 1])
        if any(argument.startswith(flag + "=") for flag in flags):
            return Path(argument.split("=", 1)[1])
    return None


def open_log():
    for directory in (logs_directory(), Path(tempfile.gettempdir()) / "Fireblade"):
        try:
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / "demarrage.log"
            if path.exists() and path.stat().st_size > 1024 * 1024:
                try:
                    path.replace(directory / "demarrage-precedent.log")
                except OSError:
                    pass  # Another open instance may still own the previous log.
            return path, path.open("a", encoding="utf-8", buffering=1)
        except OSError:
            continue
    return None, None


def failed_report(path, message, log_path):
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as output:
            json.dump(dict(status="failed", phase="startup", error=message,
                           platform=sys.platform, frozen=bool(getattr(sys, "frozen", False)),
                           log=str(log_path) if log_path else None), output, indent=2)
    except OSError:
        pass  # Never overwrite an existing report or hide the original startup error.


def notify_failure(log_path):
    if os.name != "nt":
        return
    import ctypes
    message = "Fireblade n’a pas pu démarrer."
    if log_path:
        message += f"\n\nLe journal d’erreur se trouve ici :\n{log_path}"
    ctypes.windll.user32.MessageBoxW(None, message, "Fireblade", 0x10)


def main():
    report = report_argument(sys.argv[1:])
    log_path, log = open_log() if os.name == "nt" else (None, None)
    no_console = sys.stderr is None
    if log:
        log.write(f"\n{datetime.now(timezone.utc).isoformat()} · démarrage · {sys.executable}\n")
        try:
            faulthandler.enable(file=log)
        except (OSError, RuntimeError):
            pass
        if sys.stdout is None:
            sys.stdout = log
        if sys.stderr is None:
            sys.stderr = log
    try:
        from fireblade.ui.app import main as application_main
        application_main()
    except SystemExit as exc:
        if exc.code not in (None, 0):
            failed_report(report, f"Arrêt au démarrage : code {exc.code}", log_path)
            if no_console and report is None:
                notify_failure(log_path)
        raise
    except Exception as exc:
        traceback.print_exc(file=log or sys.stderr)
        if log:
            log.flush()
        failed_report(report, str(exc) or type(exc).__name__, log_path)
        if report is None:
            notify_failure(log_path)
        raise SystemExit(1) from exc
