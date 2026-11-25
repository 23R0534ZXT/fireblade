"""Section 0.7.9: real EVTX through the whole import, including the ones that have nothing.

Copies a few logs from this machine (a busy Security log, an operational one, an empty one and
a corrupt file carrying the extension), imports them as a case, and checks the history's
verdict for each: imported with rows, or not imported with a reason.
"""

import os
import shutil
import sys
from pathlib import Path

os.environ["FIREBLADE_LANGUAGE"] = "en"
sys.path.insert(0, r"C:\fireblade-test\harness")
import fbcommon as fb  # noqa: E402

fb.prepare_environment()

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

app = QApplication(sys.argv)
fb.install_language(app)
journal = fb.Journal("evtx079")
watch = fb.ModalWatchdog(app, journal)

import fireblade.ui.collection as uic  # noqa: E402
from fireblade.ui.app import Window  # noqa: E402

SYSTEM_LOGS = Path(r"C:\Windows\System32\winevt\Logs")
ROOT = Path(r"C:\fireblade-test\evtx079")
LOGS = ROOT / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
for item in LOGS.glob("*"):
    if item.is_file():
        item.unlink()

picked = []
for name in ("Security.evtx", "Windows PowerShell.evtx", "HardwareEvents.evtx"):
    source = SYSTEM_LOGS / name
    if source.is_file():
        destination = LOGS / name
        shutil.copy2(source, destination)
        picked.append(name)
# A file that lies about what it is: nothing must crash on it.
(LOGS / "corrompu.evtx").write_bytes(b"PAS UN EVTX" * 200)
picked.append("corrompu.evtx")
print("PICKED", picked)

# The dev tree has no forensic pack: point the run at the built one, as the EXE would.
from fireblade.core.collection import ToolPack  # noqa: E402

BUILT_PACK = Path(r"C:\Users\fb\dev\fireblade\build\windows\resources\forensic-tools")
assert (BUILT_PACK / "EvtxECmd").is_dir(), BUILT_PACK

screen = fb.work_screen(app)
window = Window(require_case=False)
fb.place(window, screen)
window.setAttribute(Qt.WA_ShowWithoutActivating, True)
window.show()
window.raise_()
fb.settle(app, 700)

uic.choose_import_sources = lambda parent=None, start=None: [str(LOGS)]
window.toolpack = lambda: ToolPack(str(BUILT_PACK))


def choose_per_file(dialog):
    dialog.progressive.setChecked(True)
    return QDialog.Accepted


uic.CollectionOrganizationDialog.exec = choose_per_file
window.create_investigation("EVTX-079", "EVTX réels", "windows")
window.parse_collection()
fb.wait(app, lambda: fb.idle(window) and window.centralWidget().isEnabled(), 1200)
fb.settle(app, 2000)

report = window.collection.report
by_name = {Path(item["path"]).name: item for item in report["files"]}
for name, entry in sorted(by_name.items()):
    print("ROW", name, entry.get("status"), "|", (entry.get("reason") or "")[:120])

security = by_name.get("Security.evtx")
assert security, by_name.keys()
assert security["status"] in ("complete", "complete_with_warnings", "attention"), security
rows = sum(len(run.get("outputs") or []) for run in security.get("runs") or [])
assert rows >= 1, security
journal.add(
    "E01",
    "OK",
    "the busy log is imported with its analysis",
    None,
    {"shot": fb.shot(window, "E01-imported")},
)

empty = by_name.get("HardwareEvents.evtx")
if empty is not None:
    print("EMPTY", empty.get("status"), empty.get("reason"))
    assert empty["status"] in ("no_output", "attention"), empty
    assert "empty log" in (empty.get("reason") or "").casefold(), empty.get("reason")
    journal.add(
        "E02", "OK", "an empty log is named empty", None, {"shot": fb.shot(window, "E02-empty")}
    )

broken = by_name.get("corrompu.evtx")
assert broken is not None
print("BROKEN", broken.get("status"), (broken.get("reason") or "")[:160])
assert broken["status"] in ("error", "attention", "no_output", "unsupported"), broken
assert "unreadable" in (broken.get("reason") or "").casefold(), broken.get("reason")
journal.add(
    "E03",
    "OK",
    "a corrupt file keeps a readable reason",
    None,
    {"shot": fb.shot(window, "E03-broken")},
)

window.close()
print("SECTION OK")
