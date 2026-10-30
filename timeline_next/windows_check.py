"""Native Windows acceptance check, also executed inside the frozen EXE.

No pytest or additional runtime dependency. The report records what was actually
run; Explorer drag/drop and human use of native file pickers remain manual checks.
"""
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import struct
import sys
import tempfile
import time

import duckdb
from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QItemSelectionModel, QTimer, qVersion
from PySide6.QtWidgets import QDialog

from .app import Window
from .dialogs import ImportDialog
from .models import Filter, View
from .windows_paths import analyses_directory


def windows_memory():
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in (
                "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                "PagefileUsage", "PeakPagefileUsage")]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    kernel.K32GetProcessMemoryInfo.restype = wintypes.BOOL
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    if not kernel.K32GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return dict(peak_working_set_mib=round(counters.PeakWorkingSetSize / 1024**2, 1),
                working_set_mib=round(counters.WorkingSetSize / 1024**2, 1))


def run_check(app, report_path):
    report_path = Path(report_path).resolve()
    if report_path.exists():
        raise ValueError("Le rapport existe déjà ; choisissez un nouveau fichier.")
    report = dict(status="running", started_utc=datetime.now(timezone.utc).isoformat(),
                  platform=sys.platform, operating_system=platform.platform(),
                  machine=platform.machine(), pointer_bits=struct.calcsize("P") * 8,
                  python=sys.version.split()[0], duckdb=duckdb.__version__,
                  qt=qVersion(), pyside=pyside_version,
                  frozen=bool(getattr(sys, "frozen", False)),
                  executable=sys.executable, qt_platform=app.platformName(), checks=[],
                  not_covered=["Explorateur Windows : glisser-déposer réel", "Sélection manuelle dans les dialogues natifs",
                               "CSV forensic réels de plusieurs Go", "Partages UNC", "Essais prolongés Windows 10/11"])
    window, work = None, None
    readonly = []
    errors = []

    def expect(condition, message):
        if not condition:
            raise AssertionError(message)

    def settle(timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            app.processEvents()
            if not window.jobs and not window.pool.activeThreadCount() and (window.model is None or not window.model.jobs):
                return
            time.sleep(.005)
        raise TimeoutError("L’interface n’a pas terminé ses opérations en arrière-plan.")

    def check(name, operation):
        started = time.perf_counter()
        try:
            operation()
            expect(not errors, f"Erreurs de l’interface : {errors}")
            report["checks"].append(dict(name=name, status="passed", seconds=round(time.perf_counter() - started, 4)))
        except Exception as exc:
            report["checks"].append(dict(name=name, status="failed", error=str(exc)))
            raise

    def import_with_dialog(source, target):
        def accept_dialog():
            dialog = app.activeModalWidget()
            if not isinstance(dialog, ImportDialog):
                errors.append("La fenêtre de confirmation d’import ne s’est pas ouverte.")
                if isinstance(dialog, QDialog):
                    dialog.reject()
                return
            dialog.target.setText(str(target))
            dialog.accept()
        QTimer.singleShot(0, accept_dialog)
        window.open_path(source)

    try:
        expect(os.name == "nt" and sys.platform == "win32", "Ce contrôle exige un véritable processus Windows.")
        expect(report["pointer_bits"] == 64, "Un Python ou exécutable 64 bits est requis.")
        expect(app.platformName() == "windows", "Le plugin Qt Windows natif doit être utilisé, pas offscreen.")
        work = tempfile.TemporaryDirectory(prefix="TimelineNext vérification ")
        directory = Path(work.name)
        source = directory / "événements Windows.csv"
        with source.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.writer(output, lineterminator="\r\n")
            writer.writerow(["Artifact", "User", "RecordID", "Timestamp", "Description"])
            writer.writerows([
                ["MFT", "élève", "0001", "2026-10-30 12:00:00", "C:\\Windows\\cmd.exe"],
                ["EVTX", "bob", "9007199254740993", "2026-10-30 12:00:01", "Ligne A\nLigne B"],
                ["MFT", "élève", "2", "", "Donnée accentuée"],
            ])
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        source.chmod(stat.S_IREAD)
        readonly.append(source)
        case_path = directory / "analyse été.timeline"
        window = Window()
        window.error = errors.append  # Fail the report instead of blocking on an error modal.
        window.show()
        app.processEvents()

        def startup():
            expect(window.isVisible() and int(window.winId()) != 0, "La fenêtre Windows n’est pas visible.")
            expect(window.content_stack.currentIndex() == 0, "L’accueil doit être affiché.")
            expected_directory = analyses_directory()
            dialog = ImportDialog(source, window)
            expect(Path(dialog.target.text()).parent == expected_directory, "La destination doit être dans les données utilisateur.")
            dialog.deleteLater()
        check("native_window_and_user_data_destination", startup)

        def importing():
            import_with_dialog(source, case_path)
            settle()
            expect(window.case is not None and window.case.path == case_path, "L’analyse n’a pas été ouverte.")
            rows = window.case.page(View())
            expect(rows[0][2:4] == ("élève", "0001"), "Accents ou zéros initiaux altérés.")
            expect(rows[1][3] == "9007199254740993" and rows[1][-1] == "Ligne A\nLigne B", "Grand entier ou cellule multiligne altéré.")
            expect(hashlib.sha256(source.read_bytes()).hexdigest() == source_hash, "La source en lecture seule a changé.")
        check("readonly_utf8_bom_crlf_unicode_paths_import", importing)

        def grouping_sorting():
            window.group_column(0)
            settle()
            expect(window.case.page(window.view) == [("MFT", 2), ("EVTX", 1)], "Comptages de groupes incorrects.")
            window.group_column(1, append=True)
            settle()
            expect(window.case.page(window.view, ("MFT",)) == [("élève", 2)], "Sous-groupes incorrects.")
            window.set_view(View(sort_column=2, sort_type="number", descending=True))
            settle()
            expect([r[3] for r in window.case.page(window.view)] == ["9007199254740993", "2", "0001"], "Tri numérique inexact.")
            window.filter_value(1, "élève")
            settle()
            expect(window.case.count(window.view) == 2, "Filtre rapide incorrect.")
        check("nested_groups_exact_numeric_sort_and_filter", grouping_sorting)

        target = directory / "export vérifié.csv"
        def locked_export():
            target.write_bytes(b"previous export")
            denied = False
            with target.open("rb"):
                try:
                    window.case.export(target, View())
                except PermissionError:
                    denied = True
            expect(denied, "Le remplacement d’un fichier verrouillé devait être refusé par Windows.")
            expect(target.read_bytes() == b"previous export", "L’ancien export a été altéré.")
            expect(not target.with_name(target.name + ".partial").exists(), "Un export temporaire a été laissé après l’échec.")
            window.case.export(target, View())
            with target.open(encoding="utf-8-sig", newline="") as incoming:
                rows = list(csv.reader(incoming))
            expect(len(rows) == 4 and rows[2][2] == "9007199254740993", "L’export après déverrouillage est incorrect.")
        check("windows_locked_export_and_retry", locked_export)

        def clipboard():
            index = window.model.index(0, 0)
            window.tree.setCurrentIndex(index)
            window.tree.selectionModel().select(index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
            window.copy_rows()
            app.processEvents()
            expect("RecordID" in app.clipboard().text() and "élève" in app.clipboard().text(), "Copie Unicode dans le presse-papiers incorrecte.")
        check("windows_unicode_clipboard", clipboard)

        saved_view = View(filters=[Filter(1, "eq", "élève")], sort_column=2, sort_type="number")
        def reopen():
            window.case.bookmark(1, "À conserver")
            window.case.save_view("triage", saved_view)
            window.detach()
            moved = directory / "analyse déplacée.timeline"
            case_path.rename(moved)
            moved.rename(case_path)  # Proves the closed DB released its Windows file handle.
            window.open_path(case_path)
            settle()
            expect(window.case.bookmarks() == {1: "À conserver"}, "Signet perdu après fermeture.")
            window.set_view(window.case.views()["triage"])
            settle()
            expect(window.view == saved_view and window.case.count(window.view) == 2, "Vue persistée incorrecte.")
        check("released_file_handle_bookmarks_and_saved_view_reopen", reopen)

        def cancelled_import():
            larger = directory / "import à annuler.csv"
            block = (b"0001,alice," + b"artifact detail " * 20 + b"\r\n") * 10000
            with larger.open("wb") as output:
                output.write(b"ID,User,Description\r\n")
                for _ in range(20):
                    output.write(block)
            window.tree.setColumnHidden(5, True)
            import_with_dialog(larger, directory / "annulé.timeline")
            expect(window.busy, "L’import de contrôle s’est terminé avant la demande d’annulation.")
            window.interrupt_queries()
            settle()
            expect(window.case.path == case_path and window.view == saved_view, "L’analyse précédente n’a pas été restaurée.")
            expect(window.tree.isColumnHidden(5) and window.case.bookmarks() == {1: "À conserver"}, "Colonnes ou notes non restaurées.")
        check("cancel_import_and_restore_previous_workspace", cancelled_import)

        report["memory"] = windows_memory()
        report["status"] = "passed"
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = str(exc) or type(exc).__name__
    finally:
        if window is not None:
            try:
                if window.jobs or window.pool.activeThreadCount() or (window.model and window.model.jobs):
                    window.interrupt_queries()
                    settle(timeout=10)
                if not window.close():
                    raise RuntimeError("La fenêtre de contrôle n’a pas pu être fermée.")
            except Exception as exc:
                report["status"] = "failed"
                report["cleanup_error"] = str(exc)
        for path in readonly:
            try:
                path.chmod(stat.S_IREAD | stat.S_IWRITE)
            except OSError:
                pass
        if work is not None:
            try:
                work.cleanup()
            except OSError as exc:
                report["status"] = "failed"
                report["cleanup_error"] = str(exc)
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2, ensure_ascii=False)
    return 0 if report["status"] == "passed" else 1
