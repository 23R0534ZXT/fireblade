"""Section 0.7.9 (b): three artefact families through the same import, end to end.

Prefetch, shortcuts and event logs each go through their own reader; what must hold for all
three is the same rule: a recognised file ends imported (or with a named reason), never
silently unsupported, and every analysis it produces is readable.
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
journal = fb.Journal("artefacts079")
watch = fb.ModalWatchdog(app, journal)

import fireblade.ui.collection as uic  # noqa: E402
from fireblade.core.collection import ToolPack  # noqa: E402
from fireblade.ui.app import Window  # noqa: E402

BUILT_PACK = Path(r"C:\Users\fb\dev\fireblade\build\windows\resources\forensic-tools")
ROOT = Path(r"C:\fireblade-test\artefacts079")
LOGS = ROOT / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
for item in LOGS.glob("*"):
    if item.is_file():
        item.unlink()

SOURCES = []
for pf in sorted(Path(r"C:\Windows\Prefetch").glob("*.pf"))[:2]:
    shutil.copy2(pf, LOGS / pf.name)
    SOURCES.append(pf.name)
for lnk in sorted(Path(r"C:\Users\fb\AppData\Roaming\Microsoft\Windows\Recent").glob("*.lnk"))[:2]:
    destination = LOGS / lnk.name
    shutil.copy2(lnk, destination)
    SOURCES.append(lnk.name)
security = Path(r"C:\Windows\System32\winevt\Logs\Security.evtx")
if security.is_file():
    shutil.copy2(security, LOGS / security.name)
    SOURCES.append(security.name)
print("SOURCES", SOURCES)

screen = fb.work_screen(app)
window = Window(require_case=False)
fb.place(window, screen)
window.setAttribute(Qt.WA_ShowWithoutActivating, True)
window.show()
window.raise_()
fb.settle(app, 700)
window.toolpack = lambda: ToolPack(str(BUILT_PACK))

uic.choose_import_sources = lambda parent=None, start=None: [str(LOGS)]


def choose_per_file(dialog):
    dialog.progressive.setChecked(True)
    return QDialog.Accepted


uic.CollectionOrganizationDialog.exec = choose_per_file
window.create_investigation("ART-079", "Trois familles", "windows")
window.parse_collection()
fb.wait(app, lambda: fb.idle(window) and window.centralWidget().isEnabled(), 1500)
fb.settle(app, 2000)

report = window.collection.report
by_name = {Path(item["path"]).name: item for item in report["files"]}
for name, entry in sorted(by_name.items()):
    print("ROW", name[:40], entry.get("status"), "|", (entry.get("reason") or "")[:100])

assert set(by_name) == set(SOURCES), (set(by_name), set(SOURCES))
for name, entry in by_name.items():
    assert entry["status"] != "unsupported", (name, entry)
    assert entry["status"] != "error", (name, entry)
    outputs = sum(len(run.get("outputs") or []) for run in entry.get("runs") or [])
    print("OUT", name[:40], outputs)
    assert outputs >= 1 or entry["status"] == "no_output", (name, entry)

documents = list(window.documents)
rows = {}
for index, document in enumerate(documents):
    window.switch_document(index)
    fb.wait(app, lambda: not window.busy, 300)
    fb.settle(app, 300)
    rows[Path(document.source_info.get("path", "")).name] = window.case.db.execute(
        "SELECT count(*) FROM events"
    ).fetchone()[0]
print("ROWS", rows)
assert rows and all(rows.values()), rows
journal.add(
    "A01",
    "OK",
    f"{len(documents)} analyses, {sum(rows.values())} rows",
    None,
    {"shot": fb.shot(window, "A01-artefacts")},
)
window.close()
print("SECTION OK")
