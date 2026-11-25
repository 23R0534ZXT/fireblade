"""Section 0.7.9 (c): deleting a case from the window, certificate included.

Creates a case, imports one file, then uses the real command: the dialog is filled, the
confirmation accepted, and the case folder must be gone while the certificate exists outside.
"""
import os
import sys
from pathlib import Path

os.environ["FIREBLADE_LANGUAGE"] = "en"
sys.path.insert(0, r"C:\fireblade-test\harness")
import fbcommon as fb  # noqa: E402

fb.prepare_environment()

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

app = QApplication(sys.argv)
fb.install_language(app)
journal = fb.Journal("destroy079")
watch = fb.ModalWatchdog(app, journal)

import fireblade.ui.case_destruction_dialog as destroy_ui  # noqa: E402
import fireblade.ui.collection as uic  # noqa: E402
from fireblade.core.collection import ToolPack  # noqa: E402
from fireblade.ui.app import Window  # noqa: E402

BUILT_PACK = Path(r"C:\Users\fb\dev\fireblade\build\windows\resources\forensic-tools")
ROOT = Path(r"C:\fireblade-test\destroy079")
LOGS = ROOT / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
(LOGS / "poste.csv").write_text("User,Action\nalice,login\nbob,logout\n", encoding="utf-8")
CERTIFICATE = ROOT / "PV-destruction.pdf"
CERTIFICATE.unlink(missing_ok=True)

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
case = window.create_investigation("DESTROY-079", "À détruire", "windows")
folder = Path(window.investigation_library.folder(case["id"]))
window.parse_collection()
fb.wait(app, lambda: fb.idle(window) and window.centralWidget().isEnabled(), 900)
fb.settle(app, 1200)
assert folder.is_dir(), folder
print("CASE", folder, sum(1 for _ in folder.rglob('*') if _.is_file()), "files")

QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.Yes)


def drive(dialog):
    dialog.method.setCurrentIndex(dialog.method.findData("dod3"))
    dialog.operator.setText("Maxime MAURIN")
    dialog.witness.setText("Nicolas Malarange")
    dialog.reason.setPlainText("Clôture d'incident - test de recette")
    dialog.certificate.setText(str(CERTIFICATE))
    dialog.understood.setChecked(True)
    dialog.phrase.setText("DESTROY-079")
    fb.settle(app, 200)
    assert dialog.go.isEnabled(), dialog.status.text()
    dialog.start()
    deadline = fb.wait(app, lambda: dialog.job is None and getattr(dialog, "record", None), 600)
    fb.settle(app, 500)
    return QDialog.Accepted


destroy_ui.CaseDestructionDialog.exec = drive
window.destroy_case()
fb.settle(app, 800)

print("FOLDER EXISTS", folder.exists(), "| CERTIFICATE", CERTIFICATE.is_file())
assert not folder.exists(), "the case folder survived the destruction"
assert CERTIFICATE.is_file(), "no certificate was written"
assert CERTIFICATE.stat().st_size > 1000, CERTIFICATE.stat().st_size
assert window.active_investigation is None, window.active_investigation
journal.add("X01", "OK", "case destroyed, certificate outside", None,
            {"shot": fb.shot(window, "X01-destroyed"), "certificate": str(CERTIFICATE)})
window.close()
print("SECTION OK")
