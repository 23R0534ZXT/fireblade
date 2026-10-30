"""Optional resource smoke test for opening an existing case, not for importing."""
import argparse
import json
import os
from pathlib import Path
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import psutil
from PySide6.QtWidgets import QApplication

from timeline_next.app import Window
from timeline_next.engine import Case
from timeline_next.settings import load_settings
from timeline_next.theme import apply_theme


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cycles", type=int, default=8)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    if not args.case.is_file() or not 1 <= args.cycles <= 100:
        parser.error("An existing case and 1–100 cycles are required")
    settings = load_settings(args.config)
    process = psutil.Process()
    peak = [process.memory_info().rss]
    stop = threading.Event()
    def monitor():
        while not stop.wait(.01):
            peak[0] = max(peak[0], process.memory_info().rss)
    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    app = QApplication([])
    apply_theme(app)
    window = Window(settings)
    errors = []
    window.error = errors.append  # An error must fail the smoke test, not open a modal.
    case = None
    try:
        case = Case(args.case, settings=settings)
        info = case.info
        if not info:
            raise ValueError("The case has no completed import")
        window.attach(case)
        window.show()
        def settle():
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                app.processEvents()
                if not window.jobs and not window.model.jobs and not window.pool.activeThreadCount():
                    if errors:
                        raise RuntimeError(str(errors))
                    return
                time.sleep(.005)
            raise TimeoutError("UI did not settle")
        settle()
        window.view.groups = [min(1, len(case.headers) - 1)]
        window.apply()
        settle()
        after_collapse = []
        for _ in range(args.cycles):
            group = window.model.index(0, 0)
            window.tree.expand(group)
            settle()
            window.tree.collapse(group)
            settle()
            assert window.model.rowCount(group) == 0
            after_collapse.append(process.memory_info().rss)
        result = dict(scenario="Open existing case; group; expand/collapse first group",
                      platform=os.name, rows=info["rows"], source_bytes=info["size"],
                      cycles=args.cycles, memory_limit_mb=settings.memory_mb,
                      peak_process_rss_mib=round(peak[0] / 1024**2, 1),
                      rss_after_each_collapse_mib=[round(n / 1024**2, 1) for n in after_collapse],
                      caveat="Offscreen Qt, synthetic data, no import or real Windows measurements.")
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
    finally:
        stop.set()
        monitor_thread.join()
        window.pool.waitForDone()
        if case is not None and window.case is None:
            case.close()
        window.close()


if __name__ == "__main__":
    main()
