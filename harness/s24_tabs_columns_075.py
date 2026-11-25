"""Section 0.7.5: closing a tab keeps the analysis, and a cross hides a column.

What it proves on the real window: closing an artifact grid removes the tab but leaves the
file in the navigation tree, greyed out; double-clicking it brings the tab back with its
saved view; and the small cross on a column header hides that column.
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
journal = fb.Journal("tabs075")
watch = fb.ModalWatchdog(app, journal)

import fireblade.ui.collection as uic  # noqa: E402
from fireblade.ui.app import Window  # noqa: E402

ROOT = Path(r"C:\fireblade-test\tabs075")
LOGS = ROOT / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
for item in LOGS.glob("*.csv"):
    item.unlink()
for index, name in enumerate(("alpha", "beta", "gamma")):
    # Different content: identical files are recognised as duplicates and skipped.
    (LOGS / f"{name}.csv").write_text(
        "TimeCreated,EventId,User\n"
        f"2026-11-17 10:0{index}:00,{4624 + index},jdoe\n"
        f"2026-11-17 10:1{index}:00,{4625 + index},asmith\n",
        encoding="utf-8",
        newline="",
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
    dialog.progressive.setChecked(True)  # one tab per file
    return QDialog.Accepted


uic.CollectionOrganizationDialog.exec = choose
window.create_investigation("TABS-075", "Closed tabs", "mixed")
window.parse_collection()
fb.wait(app, lambda: fb.idle(window) and window.centralWidget().isEnabled(), 900)
fb.settle(app, 1500)

assert len(window.documents) == 3, [Path(doc.path).name for doc in window.documents]
journal.add("T01", "OK", "three tabs open", None, {"shot": fb.shot(window, "T01-tabs")})

# Close the second tab.
while not window.can_open_file():
    app.processEvents()
    fb.settle(app, 100)
window.close_document(1)
fb.settle(app, 800)

tree = window.navigator.tree
closed_items = [
    item for item in window.navigator.items() if item.data(0, Qt.UserRole + 2) == "closed"
]
opened_items = [item for item in window.navigator.items() if item.data(0, Qt.UserRole) is not None]
print("TREE closed:", [item.text(0) for item in closed_items])
print("TREE opened:", [item.text(0) for item in opened_items])
journal.add(
    "T02",
    "OK" if len(closed_items) == 1 else "FAIL",
    f"{len(window.documents)} tabs, {len(closed_items)} closed in the tree",
    None,
    {"shot": fb.shot(window, "T02-closed-in-tree")},
)
assert len(window.documents) == 2, [Path(doc.path).name for doc in window.documents]
assert len(closed_items) == 1, [item.text(0) for item in window.navigator.items()]

# Double-click it: the tab comes back.
window.navigator.activate(closed_items[0])
fb.settle(app, 800)
journal.add(
    "T03",
    "OK" if len(window.documents) == 3 else "FAIL",
    f"{len(window.documents)} tabs after reopening",
    None,
    {"shot": fb.shot(window, "T03-reopened")},
)
assert len(window.documents) == 3
assert not [item for item in window.navigator.items() if item.data(0, Qt.UserRole + 2) == "closed"]

# The cross on a column header hides that column.
header = window.tree.header()
header.resizeSection(2, 180)
fb.settle(app, 400)
close_button = header.controls[2][3]
assert close_button.text() == "×"
close_button.click()
fb.settle(app, 500)
hidden = window.tree.isColumnHidden(2)
journal.add(
    "T04",
    "OK" if hidden else "FAIL",
    f"column 2 hidden by its cross: {hidden}",
    None,
    {"shot": fb.shot(window, "T04-column-hidden")},
)
assert hidden

window.close()
print("SECTION OK")
