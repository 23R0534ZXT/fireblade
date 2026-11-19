"""Section 0.7.7: the pivot from a row, the operator glyph, and honest artefact names.

What it proves on the real window: right-clicking a PowerShell event offers "what launched
this?", and the timeline finds the process-creation event in another artefact; the filter
field carries an operator; and a parser CSV is named by its artefact, not by "amcache.csv".
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
journal = fb.Journal("pivot077")
watch = fb.ModalWatchdog(app, journal)

import fireblade.ui.collection as uic  # noqa: E402
from fireblade.core.pivot import anchor_of  # noqa: E402
from fireblade.ui.app import Window  # noqa: E402

ROOT = Path(r"C:\fireblade-test\pivot077")
LOGS = ROOT / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
for item in LOGS.glob("*.csv"):
    item.unlink()

# The script block, as PowerShell records it.
(LOGS / "powershell-4104.csv").write_text(
    'TimeCreated,EventId,Computer,Channel,ScriptBlockText\n'
    '"2026-11-17 10:04:12",4104,SRV-DC01,Microsoft-Windows-PowerShell/Operational,'
    '"powershell.exe -enc SQBFAFgAIABOAGUAdwAtAE8AYgBqAGUAYwB0AA=="\n'
    '"2026-11-17 10:09:40",4104,SRV-DC01,Microsoft-Windows-PowerShell/Operational,'
    '"Get-ChildItem C:\\Users"\n', encoding="utf-8", newline="")

# The process creation, forty seconds earlier, in another artefact.
(LOGS / "sysmon-1.csv").write_text(
    'UtcTime,Computer,Image,ParentImage,CommandLine\n'
    '"2026-11-17 10:03:32",SRV-DC01,C:\\Windows\\System32\\cmd.exe,'
    'C:\\Windows\\explorer.exe,"cmd.exe /c whoami"\n'
    '"2026-11-17 10:03:55",SRV-DC01,'
    'C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe,'
    'C:\\Windows\\System32\\cmd.exe,"powershell.exe -enc SQBFAFgAIABOAGUAdwAtAE8AYgBqAGUAYwB0AA=="\n',
    encoding="utf-8", newline="")

# A parser CSV whose name says nothing, and one whose name says everything.
(LOGS / "amcache.csv").write_text(
    'Application Name,SHA1,File Path\nupdate.exe,aabb,C:\\Temp\\u.exe\n', encoding="utf-8")
(LOGS / "export.csv").write_text(
    'Application Name,SHA1,File Path\nsetup.exe,ccdd,C:\\Temp\\s.exe\n', encoding="utf-8")

screen = fb.work_screen(app)
window = Window(require_case=False)
fb.place(window, screen)
window.setAttribute(Qt.WA_ShowWithoutActivating, True)
window.show()
window.raise_()
fb.settle(app, 700)

uic.choose_import_sources = lambda parent=None, start=None: [str(LOGS)]


def choose_per_file(dialog):
    dialog.progressive.setChecked(True)
    return QDialog.Accepted


uic.CollectionOrganizationDialog.exec = choose_per_file
window.create_investigation("PIVOT-077", "Pivot", "windows")
window.parse_collection()
fb.wait(app, lambda: fb.idle(window) and window.centralWidget().isEnabled(), 900)
fb.settle(app, 1500)

titles = [item.text(0) for item in window.navigator.items() if item.data(0, Qt.UserRole) is not None]
print("TITLES", titles)
assert any(title.startswith("Amcache") for title in titles), titles
assert not any("amcache.csv" == title for title in titles), titles
journal.add("V01", "OK", "artefact named by what it holds", None,
            {"shot": fb.shot(window, "V01-labels")})

# The pivot: from the PowerShell row, find what launched it.
window.switch_document(next(i for i, doc in enumerate(window.documents)
                            if "powershell-4104" in str(doc.source_info.get("path", ""))))
fb.settle(app, 800)
anchor = anchor_of(list(window.case.headers), list(window.model.node(window.model.index(0, 0)).values[1:]))
print("ANCHOR", anchor)
assert anchor and anchor["token"] == "powershell.exe", anchor
assert anchor["host"] == "SRV-DC01", anchor

window.pivot_launch(anchor)
fb.wait(app, lambda: fb.idle(window), 600)
fb.settle(app, 1500)
panel = window.timeline_panel
rows = [panel.model.rows[i] for i in range(panel.model.rowCount())]
print("PIVOT ROWS", len(rows))
print("STATS", panel.stats.text().replace("\n", " | ")[:300])
print("QUERY", panel.query.text(), "NOTE", bool(getattr(panel, "pivot_note", None)))
assert panel.query.text() == "powershell.exe", panel.query.text()
assert rows, "the pivot found nothing in the other artefacts"
joined = " ".join(str(cell) for row in rows for cell in row)
assert "powershell.exe" in joined.casefold(), joined[:400]
sources = {str(panel.documents[row[0]].source_info.get("path", "")) for row in rows}
print("PIVOT SOURCES", sources)
assert any("sysmon" in path for path in sources), sources
journal.add("V02", "OK" if rows else "FAIL", f"{len(rows)} event(s) around the launch", None,
            {"shot": fb.shot(window, "V02-pivot")})

# The operator glyph beside a column field.
window.workbench.setCurrentIndex(0)
fb.settle(app, 600)
header = window.tree.header()
assert header.operators, "no operator button"
value = str(window.model.node(window.model.index(0, 0)).values[1])
header.controls[1][0].setText(value)
header.set_operator(0, 1, "eq", "Égal à (exact)")
fb.settle(app, 900)
applied = [(f.column, f.operator, f.value) for f in window.view.filters]
print("FILTERS", applied)
assert applied == [(0, "eq", value)], applied
journal.add("V03", "OK", f"operator in use: {applied}", None,
            {"shot": fb.shot(window, "V03-operator")})

window.close()
print("SECTION OK")
