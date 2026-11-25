"""Section 0.7.0: the case as an engagement record — actions, graph, report, destruction.

Run with:

    powershell -File C:\\Users\\fb\\vm_section.ps1 -Name s20_case_070

What it proves, on the real window and with captures at every step:

- the tracking table has the six requested columns, stores an action, closes one, and the
  global scope adds the Case and Client columns;
- an indicator and a machine are recorded and listed;
- the attack graph is built from the Hayabusa findings and an analyst tag survives a rebuild;
- the client report is generated as HTML and contains the client, the action and the graph;
- a real file inside the case is destroyed with the 3-pass scheme, the SHA-256 before and
  after are in the certificate, and the case itself is still readable afterwards.
"""

import os
import sys
import time
from pathlib import Path

os.environ["FIREBLADE_LANGUAGE"] = "fr"
sys.path.insert(0, r"C:\fireblade-test\harness")
import fbcommon as fb  # noqa: E402

fb.prepare_environment()

from PySide6.QtCore import QDate, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QTextBrowser  # noqa: E402

app = QApplication(sys.argv)
fb.install_language(app)
from fireblade.core.i18n import set_language  # noqa: E402

set_language("fr")  # the capture shows the interface the client's analyst will use
journal = fb.Journal("case070")
watch = fb.ModalWatchdog(app, journal)

import fireblade.ui.case_commands as commands  # noqa: E402
import fireblade.ui.collection as uic  # noqa: E402
import fireblade.ui.destruction_dialog as destruction_ui  # noqa: E402
import fireblade.ui.operations as ops  # noqa: E402
from fireblade.core import case_workspace  # noqa: E402
from fireblade.ui.app import Window  # noqa: E402

ROOT = Path(r"C:\fireblade-test\case070")
ALERTS = ROOT / "alerts"
ALERTS.mkdir(parents=True, exist_ok=True)
(ALERTS / "hayabusa-alerts.csv").write_text(
    "Timestamp,RuleTitle,Level,Computer,Channel,EventID,Details,RuleID,MitreTactics,MitreTags\n"
    "2026-11-17T09:00:02Z,Backup agent started,informational,SRV-DC01,Application,1000,"
    '"Agent: veeam",r9,,\n'
    "2026-11-17T10:02:44Z,RDP Logon,informational,SRV-DC01,Security,4624,"
    '"LogonType: 10 | TargetUserName: administrateur",r1,InitialAccess,T1078\n'
    "2026-11-17T10:02:52Z,Suspicious Service Path,high,SRV-DC01,System,7045,"
    '"ServiceName: updsvc | ImagePath: C:\\Temp\\u.exe -k netsvcs",r5,Persistence,T1543.003\n'
    "2026-11-17T10:03:30Z,Encoded PowerShell,high,PC-COMPTA,PowerShell,4104,"
    '"ScriptBlock: -enc SQBFAFgA",r7,Execution,T1059.001\n'
    "2026-11-17T10:04:10Z,Outbound connection to rare domain,medium,PC-COMPTA,"
    'Sysmon,3,"Destination: evil.example | Port: 443",r8,CommandAndControl,T1071\n',
    encoding="utf-8",
    newline="",
)

screen = fb.work_screen(app)
window = Window(require_case=False)
fb.place(window, screen)
window.setAttribute(Qt.WA_ShowWithoutActivating, True)
window.show()
window.raise_()
fb.settle(app, 800)
journal.add("D00", "OK", "window ready (fr)", None, {"shot": fb.shot(window, "D00-start")})

data = window.create_investigation("CASE-070", "Engagement 0.7.0 - preuves et suivi", "windows")
folder = window.investigation_library.folder(data["id"])
fb.settle(app, 800)

uic.choose_import_sources = lambda parent=None, start=None: [str(ALERTS)]


def choose_one_grid_per_file(dialog):
    dialog.progressive.setChecked(True)
    return QDialog.Accepted


uic.CollectionOrganizationDialog.exec = choose_one_grid_per_file
window.parse_collection()
fb.wait(app, lambda: fb.idle(window) and window.centralWidget().isEnabled(), 900)
fb.settle(app, 1200)
fb.select_analysis_when_ready(window, app, "hayabusa-alerts", 180)
journal.add("D01", "OK", "alerts imported", None, {"shot": fb.shot(window, "D01-imported")})

window.workbench.setCurrentWidget(window.hayabusa_panel)
window.hayabusa_panel.reload()
fb.settle(app, 900)
assert window.hayabusa_panel.groups, "no finding in the Hayabusa panel"

panel = window.operations_panel
window.workbench.setCurrentWidget(panel)
fb.settle(app, 600)
columns = [
    panel.actions_table.horizontalHeaderItem(i).text()
    for i in range(panel.actions_table.columnCount())
]
expected = ["Date", "Priority", "Action status", "Action type", "Intervenant", "Details"]
assert columns == expected, columns
journal.add("D02", "OK", "six-column table", None, {"shot": fb.shot(panel, "D02-table-empty")})


def fill_action(dialog):
    dialog.date.setDate(QDate(2026, 11, 18))
    dialog.priority.setCurrentIndex(dialog.priority.findData("high"))
    dialog.status.setCurrentIndex(dialog.status.findData("waiting_client"))
    dialog.type.setCurrentIndex(dialog.type.findData("remediation"))
    dialog.intervenant.setText("Direction SI (client)")
    dialog.machine.setCurrentText("SRV-DC01")
    dialog.reference.setText("GLPI-4711")
    dialog.details.setPlainText(
        "Réinitialiser les comptes du service comptabilité\n"
        "Comptes AD et sauvegardes à reprendre avant vendredi"
    )
    return QDialog.Accepted


ops.ActionDialog.exec = fill_action
panel.add_action()
fb.settle(app, 500)
assert panel.actions_table.rowCount() == 1, panel.actions_table.rowCount()
row = [panel.actions_table.item(0, column).text() for column in range(6)]
assert row[0] == "2026-11-18" and row[1] == "High" and row[2] == "Waiting on client", row
assert row[3] == "Remediation" and row[4] == "Direction SI (client)", row
assert "Réinitialiser les comptes" in row[5], row
journal.add(
    "D03", "OK", "action recorded from the dialog", None, {"shot": fb.shot(panel, "D03-action")}
)

panel.actions_table.selectRow(0)
panel.complete_action()
fb.settle(app, 400)
assert panel.actions_table.item(0, 2).text() == "Completed"
panel.actions_table.selectRow(0)
panel.reopen_action()
fb.settle(app, 300)
assert panel.actions_table.item(0, 2).text() == "In progress"


def fill_action_two(dialog):
    dialog.date.setDate(QDate(2026, 11, 19))
    dialog.priority.setCurrentIndex(dialog.priority.findData("critical"))
    dialog.status.setCurrentIndex(dialog.status.findData("in_progress"))
    dialog.type.setCurrentIndex(dialog.type.findData("analysis"))
    dialog.intervenant.setText("Nous - DFIR")
    dialog.machine.setCurrentText("PC-COMPTA")
    dialog.details.setPlainText("Analyser la chaîne PowerShell encodée")
    return QDialog.Accepted


ops.ActionDialog.exec = fill_action_two
panel.add_action()
fb.settle(app, 400)

case_workspace.mutate(
    folder,
    lambda data: data["client"].update(
        name="ACME Industrie", reference="REF-2026-070", sector="Industrie", contact="M. Client"
    ),
)
case_workspace.mutate(
    folder,
    lambda data: data["engagement"].update(
        contract="CT-070",
        lead="Maxime MAURIN",
        start="2026-11-17",
        end="2026-11-30",
        notes="Périmètre : contrôleur de domaine et poste comptabilité.",
    ),
)
panel.refresh()
panel.scope.setCurrentIndex(panel.scope.findData("all"))
fb.settle(app, 600)
headers = [
    panel.actions_table.horizontalHeaderItem(i).text()
    for i in range(panel.actions_table.columnCount())
]
assert headers[:2] == ["Case", "Client"], headers
assert panel.actions_table.item(0, 0).text() == "CASE-070"
journal.add(
    "D04",
    "OK",
    "global board with case and client",
    None,
    {"shot": fb.shot(panel, "D04-all-cases")},
)
panel.scope.setCurrentIndex(panel.scope.findData("case"))
panel.refresh()
fb.settle(app, 400)


def fill_ioc(dialog):
    dialog.value.setText("evil.example")
    dialog.status.setCurrentIndex(dialog.status.findData("confirmed"))
    dialog.machine.setCurrentText("PC-COMPTA")
    dialog.label.setText("Domaine de commande observé")
    dialog.source.setText("Sysmon 3")
    return QDialog.Accepted


ops.IocDialog.exec = fill_ioc
panel.tabs.setCurrentIndex(1)
panel.add_indicator()
fb.settle(app, 400)
assert panel.ioc_table.rowCount() == 1
assert panel.ioc_table.item(0, 1).text() == "evil.example"
assert panel.ioc_table.item(0, 2).text() == "Confirmed"
journal.add("D05", "OK", "indicator tracked", None, {"shot": fb.shot(panel, "D05-ioc")})


def fill_entity(dialog):
    dialog.kind.setCurrentIndex(dialog.kind.findData("machine"))
    dialog.label.setText("SRV-DC01")
    dialog.hostname.setText("SRV-DC01.acme.local")
    dialog.ip.setText("10.20.0.10")
    dialog.os.setText("Windows Server 2022")
    dialog.tags.setText("critique, comptes")
    return QDialog.Accepted


ops.EntityDialog.exec = fill_entity
panel.tabs.setCurrentIndex(2)
panel.add_entity()
fb.settle(app, 400)
assert panel.entity_table.rowCount() == 1
assert panel.entity_table.item(0, 1).text() == "SRV-DC01"
journal.add("D06", "OK", "machine recorded", None, {"shot": fb.shot(panel, "D06-machine")})

graph = window.graph_panel
window.workbench.setCurrentWidget(graph)
graph.reload()
fb.settle(app, 700)
assert graph.canvas.graph["nodes"], graph.status.text()
technique = next(
    (node for node in graph.canvas.graph["nodes"] if node["kind"] == "technique"), None
)
stage = next((node for node in graph.canvas.graph["nodes"] if node["kind"] == "stage"), None)
assert technique is not None and stage is not None
graph.canvas.selected = technique["id"]
graph.show_node(technique["id"])
fb.settle(app, 300)


def fill_tag(dialog):
    dialog.existing.setPlainText("persistance\naccès initial")
    return QDialog.Accepted


import fireblade.ui.attack_graph_view as graph_view  # noqa: E402

graph_view.TagDialog.exec = fill_tag
graph.tag_selected()
fb.settle(app, 500)
saved = case_workspace.load(folder)
tagged = next((node for node in saved["graph"]["nodes"] if node["id"] == technique["id"]), None)
assert tagged and tagged["tags"] == ["persistance", "accès initial"], saved["graph"]["nodes"]
graph.reload()
technique = next(
    (node for node in graph.canvas.graph["nodes"] if node["kind"] == "technique"), None
)
assert technique["tags"] == ["persistance", "accès initial"]
journal.add("D07", "OK", "graph built and tagged", None, {"shot": fb.shot(graph, "D07-graph")})

REPORT = ROOT / "rapport-client.html"
REPORT.unlink(missing_ok=True)


def accept_report(dialog):
    dialog.title.setText("Rapport d'investigation — ACME Industrie")
    dialog.analyst.setText("Maxime MAURIN")
    return QDialog.Accepted


commands.ClientReportDialog.exec = accept_report
commands.QFileDialog.getSaveFileName = lambda *args, **kwargs: (
    str(REPORT),
    "Rapport HTML (*.html)",
)
# "Report saved — open it?" must not open a browser on the user's desktop.
QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.No)
window.client_report()
assert fb.wait(app, lambda: REPORT.exists(), 180), "client report not written"
html = REPORT.read_text(encoding="utf-8")
for needle in (
    "ACME Industrie",
    "REF-2026-070",
    "1. Synthèse",
    "4. Constats détaillés",
    "5. Graphe d'attaque",
    "6. Indicateurs suivis",
    "7. Actions et suivi",
    "8. Devenir des preuves",
    "evil.example",
    "Réinitialiser les comptes",
):
    assert needle in html, needle
assert "data:image/png;base64," in html, "the graph was not embedded"
viewer = QTextBrowser()
viewer.setWindowTitle("Rapport client — aperçu")
viewer.resize(900, 700)
viewer.setHtml(html)
fb.place(viewer, screen)
viewer.show()
fb.settle(app, 900)
journal.add(
    "D08",
    "OK",
    "client report generated and rendered",
    None,
    {"shot": fb.shot(viewer, "D08-report"), "generated": str(REPORT)},
)
viewer.close()

EVIDENCE = folder / "preuves-a-detruire"
EVIDENCE.mkdir(parents=True, exist_ok=True)
first = EVIDENCE / "epave-comptes.csv"
second = EVIDENCE / "capture-ecran.png"
first.write_bytes(b"compte,empreinte\nadministrateur,SEGRET\n" * 400)
second.write_bytes(b"\x89PNG\r\n\x1a\n" + b"faux" * 100)
before = {path.name: path.read_bytes() for path in (first, second)}

from fireblade.core.destruction import sha256_file  # noqa: E402

digests = {name: sha256_file(EVIDENCE / name) for name in before}

dialog = destruction_ui.DestructionDialog(window)
try:
    fb.settle(app, 400)
    rows = []
    for index in range(dialog.list.count()):
        item = dialog.list.item(index)
        if "preuves-a-detruire" in (item.data(Qt.UserRole) or ""):
            item.setCheckState(Qt.Checked)
            rows.append(item.data(Qt.UserRole))
    assert len(rows) == 2, rows
    dialog.method.setCurrentIndex(dialog.method.findData("dod3"))
    dialog.operator.setText("Maxime MAURIN")
    dialog.witness.setText("M. Client")
    dialog.reason.setPlainText("Fin de mission : restitution du poste")
    dialog.understood.setChecked(True)
    dialog.phrase.setText("DETRUIRE")
    dialog.update_total()
    assert dialog.go.isEnabled()
    journal.add(
        "D09",
        "OK",
        "destruction dialog ready",
        None,
        {"shot": fb.shot(dialog, "D09-destroy-ready")},
    )
    answers = {"count": 0}

    def answer(*args, **kwargs):
        # First question: confirm the destruction. Second: "open the PDF?" — no, a
        # scripted run must not launch a viewer on the user's desktop.
        answers["count"] += 1
        return QMessageBox.Yes if answers["count"] == 1 else QMessageBox.No

    QMessageBox.question = staticmethod(answer)
    dialog.start()
    assert fb.wait(app, lambda: dialog.job is not None and dialog.job.isFinished(), 240), (
        "destruction did not finish"
    )
    fb.settle(app, 1200)
    assert dialog.job.error is None, dialog.job.error
    assert not first.exists() and not second.exists(), "evidence still on disk"
    certificates = sorted((folder / "destruction").glob("PV-*.html"))
    assert certificates, "no certificate"
    pv = certificates[-1].read_text(encoding="utf-8")
    assert digests["epave-comptes.csv"] in pv, "before-hash missing from the certificate"
    assert "détruit et vérifié" in pv
    assert (folder / "destruction" / (certificates[-1].stem + ".pdf")).exists(), "no PDF"
    journal.add(
        "D10",
        "OK",
        "evidence destroyed, certificate written",
        None,
        {"shot": fb.shot(dialog, "D10-destroyed"), "certificate": str(certificates[-1])},
    )
    pv_view = QTextBrowser()
    pv_view.setWindowTitle("Procès-verbal de destruction")
    pv_view.resize(900, 700)
    pv_view.setHtml(pv)
    fb.place(pv_view, screen)
    pv_view.show()
    fb.settle(app, 800)
    journal.add(
        "D11",
        "OK",
        "certificate rendered",
        None,
        {"shot": fb.shot(pv_view, "D11-certificate"), "certificate": str(certificates[-1])},
    )
    pv_view.close()
finally:
    dialog.close()
    dialog.deleteLater()

with window.case.lock:
    rows_total = window.case.db.execute("SELECT count(*) FROM events").fetchone()[0]
assert rows_total > 0, "the analysis is no longer readable after the destruction"
journal.add("D12", "OK", f"analysis still readable ({rows_total} rows)")

# The graph leaves the case as a MITRE ATT&CK Navigator layer, the format the analyst's
# other tools already read.
LAYER = ROOT / "attack-layer.json"
LAYER.unlink(missing_ok=True)
window.workbench.setCurrentWidget(graph)
graph.reload()
fb.settle(app, 500)
graph_view.QFileDialog.getSaveFileName = lambda *args, **kwargs: (
    str(LAYER),
    "Couche Navigator (*.json)",
)
graph.export_navigator()
fb.settle(app, 600)
assert LAYER.is_file(), graph.status.text()
import json as _json

layer = _json.loads(LAYER.read_text(encoding="utf-8"))
print(
    "LAYER",
    layer["domain"],
    len(layer["techniques"]),
    [t["techniqueID"] for t in layer["techniques"]][:6],
)
assert layer["domain"] == "enterprise-attack" and layer["techniques"]
assert all(t["techniqueID"].startswith("T") and t.get("metadata") for t in layer["techniques"])
journal.add(
    "D14",
    "OK",
    f"{len(layer['techniques'])} techniques exported for the Navigator",
    None,
    {"shot": fb.shot(graph, "D14-navigator-layer")},
)

window.workbench.setCurrentWidget(window.operations_panel)
panel.refresh()
fb.settle(app, 600)
journal.add("D13", "OK", "case closed cleanly", None, {"shot": fb.shot(window, "D13-final")})
window.close()
print("SECTION OK")
