"""Section 0.7.4: the import tells where it stands, percentage included.

What it proves on the real window: while a folder of forty files is read, the Imports
panel shows a percentage that rises, the file being read, the rows already written and an
estimate of what is left; at the end the line disappears and the report holds 100 %.
"""

import os
import sys
import time
from pathlib import Path

os.environ["FIREBLADE_LANGUAGE"] = "en"
sys.path.insert(0, r"C:\fireblade-test\harness")
import fbcommon as fb  # noqa: E402

fb.prepare_environment()

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

app = QApplication(sys.argv)
fb.install_language(app)
journal = fb.Journal("progress074")
watch = fb.ModalWatchdog(app, journal)

import fireblade.ui.collection as uic  # noqa: E402
from fireblade.ui.app import Window  # noqa: E402

ROOT = Path(r"C:\fireblade-test\progress074")
LOGS = ROOT / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
for item in LOGS.glob("*.csv"):
    item.unlink()

FILES = 40
ROWS = 4000
for index in range(FILES):
    with (LOGS / f"events-{index:02d}.csv").open("w", encoding="utf-8", newline="") as stream:
        stream.write("TimeCreated,EventId,Channel,Computer\n")
        for row in range(ROWS):
            stream.write(
                f"2026-11-17 10:{row // 60 % 60:02d}:{row % 60:02d},{4600 + index % 40},C{index},SRV-{index % 5}\n"
            )

screen = fb.work_screen(app)
window = Window(require_case=False)
fb.place(window, screen)
window.setAttribute(Qt.WA_ShowWithoutActivating, True)
window.show()
window.raise_()
fb.settle(app, 700)

uic.choose_import_sources = lambda parent=None, start=None: [str(LOGS)]


def choose(dialog):
    dialog.artifacts.setChecked(True)
    return QDialog.Accepted


uic.CollectionOrganizationDialog.exec = choose

window.create_investigation("PROGRESS-074", "Import progress", "mixed")
window.parse_collection()

samples = []
deadline = time.monotonic() + 300
while time.monotonic() < deadline:
    app.processEvents()
    state = (window.collection.report if window.collection else {}).get("progress") or {}
    if state:
        sample = (state.get("done"), state.get("percent"), state.get("current"), state.get("rows"))
        if not samples or samples[-1][:2] != sample[:2]:
            samples.append(sample)
            print("SAMPLE", sample, flush=True)
        if (state.get("percent") or 0) >= 40 and not globals().get("_mid_shot"):
            globals()["_mid_shot"] = True
            window.workbench.setCurrentIndex(1)
            fb.settle(app, 600)
            print(
                "MID",
                state.get("percent"),
                window.collection_report.progress_text.text(),
                flush=True,
            )
            journal.add(
                "P00",
                "OK",
                "progress line while the import runs",
                None,
                {"shot": fb.shot(window, "P00-progress")},
            )
            window.workbench.setCurrentIndex(0)
    if (
        all(getattr(window, "disk_job", None) is None for _ in (0,))
        and fb.idle(window)
        and window.documents
    ):
        break
    fb.settle(app, 200)

fb.wait(app, lambda: fb.idle(window) and window.centralWidget().isEnabled(), 900)
fb.settle(app, 1500)

print("SAMPLES", len(samples))
journal.add(
    "P01",
    "OK" if len(samples) >= 4 else "FAIL",
    f"{len(samples)} progress samples",
    None,
    {"shot": fb.shot(window, "P01-progress")},
)

percents = [percent for _done, percent, _current, _rows in samples]
assert percents, "no progress was published"
assert max(percents) >= 99.0, percents
assert len(samples) >= 4, samples
assert any(current for _done, _percent, current, _rows in samples), samples

final = window.collection.report.get("progress") or {}
assert final.get("finished") and final.get("percent") == 100.0, final
assert final.get("done") == final.get("total") == FILES, final

documents = list(window.documents)
journal.add(
    "P02",
    "OK" if len(documents) == 1 else "FAIL",
    f"{len(documents)} merged grid(s), {final.get('percent')} % at the end",
    None,
    {"shot": fb.shot(window, "P02-done")},
)
assert len(documents) == 1, [Path(doc.path).name for doc in documents]
assert not window.collection_report.progress_widget.isVisible()
window.close()
print("SECTION OK")
