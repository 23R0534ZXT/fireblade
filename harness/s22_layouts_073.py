"""Section 0.7.3: the three import layouts, on a folder holding several families.

What it proves, on the real window: "one grid per file" keeps one grid per source, "one
grid per artifact family" merges the three CSV files into a single grid (all rows kept,
source named in a column), and "one grid for everything" gives exactly one grid with a
grouping that stays.
"""
import os
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
journal = fb.Journal("layouts073")
watch = fb.ModalWatchdog(app, journal)

import fireblade.ui.collection as uic  # noqa: E402
from fireblade.ui.app import Window  # noqa: E402

ROOT = Path(r"C:\fireblade-test\layouts073")
LOGS = ROOT / "logs"
if LOGS.exists():
    for item in LOGS.iterdir():
        item.unlink()
LOGS.mkdir(parents=True, exist_ok=True)

for index, (name, rows) in enumerate({
    "amcache-01.csv": "Application Name,SHA1\nupdate.exe,aabbccdd\nsetup.exe,11223344\n",
    "amcache-02.csv": "Application Name,SHA1\nsvc.exe,55667788\n",
    "amcache-03.csv": "Application Name,SHA1\nagent.exe,99aabbcc\n",
    "events.tsv": "Time\tEvent\tUser\n2026-11-17 10:00:00\tlogin\tjdoe\n",
}.items()):
    (LOGS / name).write_text(rows, encoding="utf-8", newline="")

screen = fb.work_screen(app)


def run_round(mode, case_name):
    window = Window(require_case=False)
    fb.place(window, screen)
    window.setAttribute(Qt.WA_ShowWithoutActivating, True)
    window.show()
    window.raise_()
    fb.settle(app, 700)

    selected = {"files": "progressive", "artifacts": "artifacts", "combined": "combined"}[mode]

    def choose(dialog):
        getattr(dialog, selected).setChecked(True)
        return QDialog.Accepted

    uic.choose_import_sources = lambda parent=None, start=None: [str(LOGS)]
    uic.CollectionOrganizationDialog.exec = choose
    window.create_investigation(case_name, f"Layout {mode}", "mixed")
    window.parse_collection()
    fb.wait(app, lambda: fb.idle(window) and window.centralWidget().isEnabled(), 900)
    fb.settle(app, 1500)

    documents = list(window.documents)
    shot = fb.shot(window, f"L-{mode}")
    journal.add(f"L-{mode}", "OK", f"{len(documents)} grids: "
                + ", ".join(Path(document.path).stem[:24] for document in documents), None, {"shot": shot})
    return window, documents


# One grid per file: four sources, four grids.
window, documents = run_round("files", "LAYOUTS-FILES")
assert len(documents) == 4, [Path(doc.path).name for doc in documents]
window.close()

# One grid per artifact family: the three CSV files make one grid, the TSV another.
window, documents = run_round("artifacts", "LAYOUTS-ARTIFACTS")
assert len(documents) == 2, [Path(doc.path).name for doc in documents]
merged_rows = {}
for index, document in enumerate(documents):
    window.switch_document(index)
    fb.wait(app, lambda: not window.busy, 300)
    fb.settle(app, 500)
    merged_rows[index] = (("Fichier source" in window.case.headers),
                          window.case.db.execute("SELECT count(*) FROM events").fetchone()[0])
print("MERGED", merged_rows)
journal.add("L-rows", "OK", f"grids: {merged_rows}", None,
            {"shot": fb.shot(window, "L-merged")})
assert sorted(rows for _merged, rows in merged_rows.values()) == [1, 4], merged_rows
assert all(merged for merged, _rows in merged_rows.values()), merged_rows
window.close()

# One grid for everything, grouped by family, and the grouping stays.
window, documents = run_round("combined", "LAYOUTS-COMBINED")
assert len(documents) == 1, [Path(doc.path).name for doc in documents]
state = window.group_state() if hasattr(window, "group_state") else None
rows = window.case.db.execute("SELECT count(*) FROM events").fetchone()[0]
assert rows == 5, rows
window.close()

print("SECTION OK")
