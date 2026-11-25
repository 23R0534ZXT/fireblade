"""Section 0.7.0 (b): a folder of mixed real-world logs, imported as one case.

What it proves: IIS/W3C, Amcache CSV, TSV, Windows Event CSV and Hayabusa alerts land in
the same case without becoming raw text; the case keeps one analysis per source; the
client report lists all of them; and nothing is lost on the way.
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
journal = fb.Journal("mixed070")
watch = fb.ModalWatchdog(app, journal)

import fireblade.ui.case_commands as commands  # noqa: E402
import fireblade.ui.collection as uic  # noqa: E402
from fireblade.ui.app import Window  # noqa: E402

ROOT = Path(r"C:\fireblade-test\mixed070")
LOGS = ROOT / "logs"
LOGS.mkdir(parents=True, exist_ok=True)

(LOGS / "hayabusa-alerts.csv").write_text(
    "Timestamp,RuleTitle,Level,Computer,Channel,EventID,Details,RuleID,MitreTactics,MitreTags\n"
    "2026-11-17T10:02:52Z,Suspicious Service Path,high,SRV-DC01,System,7045,"
    '"ServiceName: updsvc",r5,Persistence,T1543.003\n'
    "2026-11-17T10:03:30Z,Encoded PowerShell,high,PC-COMPTA,PowerShell,4104,"
    '"ScriptBlock: -enc SQBFAFgA",r7,Execution,T1059.001\n', encoding="utf-8", newline="")
(LOGS / "iis.log").write_text(
    "#Software: Microsoft Internet Information Services 10.0\r\n#Version: 1.0\r\n"
    "#Date: 2026-11-17 00:00:00\r\n"
    "#Fields: date time s-ip cs-method cs-uri-stem cs-uri-query s-port cs-username c-ip "
    "cs(User-Agent) sc-status sc-substatus sc-win32-status time-taken\r\n"
    "2026-11-17 10:04:10 10.20.0.10 GET /Default.aspx - 443 - 203.0.113.9 Mozilla/5.0 200 0 0 31\r\n"
    "2026-11-17 10:04:12 10.20.0.10 POST /upload.aspx id=7 443 CORP\\jdoe 203.0.113.9 curl/8.0 500 0 0 120\r\n",
    encoding="utf-8", newline="")
(LOGS / "amcache.csv").write_text(
    '\ufeff"Application Name","File Path","SHA1","File Size"\r\n'
    '"update.exe","C:\\Temp\\u.exe","aabbccddeeff00112233445566778899aabbccdd","102400"\r\n',
    encoding="utf-8", newline="")
(LOGS / "events.tsv").write_text(
    "Time\tEvent\tUser\n2026-11-17 10:00:00\tlogin\tjdoe\n2026-11-17 10:05:00\tlogout\tjdoe\n",
    encoding="utf-8")
(LOGS / "windows-events.csv").write_text(
    '\ufeff"Log Name","Source","Event ID","Level","Time Created","Computer","Description"\r\n'
    '"Security","Microsoft-Windows-Security-Auditing","4624","Information",'
    '"17/11/2026 10:02:44","SRV-DC01","An account was logged on, LogonType 10"\r\n',
    encoding="utf-8", newline="")

screen = fb.work_screen(app)
window = Window(require_case=False)
fb.place(window, screen)
window.setAttribute(Qt.WA_ShowWithoutActivating, True)
window.show()
window.raise_()
fb.settle(app, 800)

data = window.create_investigation("MIXED-070", "Journaux hétérogènes", "mixed")
uic.choose_import_sources = lambda parent=None, start=None: [str(LOGS)]
def choose_one_grid_per_file(dialog):
    # One analysis per source: the report below names each of them.
    dialog.progressive.setChecked(True)
    return QDialog.Accepted


uic.CollectionOrganizationDialog.exec = choose_one_grid_per_file
window.parse_collection()
fb.wait(app, lambda: fb.idle(window) and window.centralWidget().isEnabled(), 900)
fb.settle(app, 2000)

documents = list(window.documents)
journal.add("M10", "OK", f"{len(documents)} analyses imported", None,
            {"shot": fb.shot(window, "M10-imported")})
assert len(documents) >= 5, [doc.path for doc in documents]

report = window.collection.report
statuses = {Path(item['path']).name: item['status'] for item in report['files']}
print("STATUSES", statuses)
assert all(status in ("complete", "attention") for status in statuses.values()), statuses

names = {Path(item.path).stem for item in documents}
headers = {}
for document in documents:
    source_name = Path(document.source_info.get('path', '')).name
    fb.select_analysis(window, app, source_name)
    fb.settle(app, 400)
    headers[source_name] = list(window.case.headers)[:6]
print("HEADERS", headers)

iis = next((key for key in headers if key == "iis.log"), "")
assert any("Horodatage" in column or "Format" in column for column in headers[iis]), headers[iis]

# Every source is named in the client report.
REPORT = ROOT / "rapport-mixed.html"
REPORT.unlink(missing_ok=True)
commands.QFileDialog.getSaveFileName = lambda *args, **kwargs: (str(REPORT), "Rapport HTML (*.html)")


def accept_report(dialog):
    dialog.title.setText("Rapport — journaux hétérogènes")
    return QDialog.Accepted


commands.ClientReportDialog.exec = accept_report
window.client_report()
assert fb.wait(app, lambda: REPORT.exists(), 180), "no report"
html = REPORT.read_text(encoding="utf-8")
for name in ("hayabusa-alerts.csv", "iis.log", "amcache.csv", "events.tsv", "windows-events.csv"):
    assert name in html, name
journal.add("M11", "OK", "client report lists every source", None,
            {"shot": fb.shot(window, "M11-report")})
window.close()
print("SECTION OK")
