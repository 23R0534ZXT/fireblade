"""Section E/F: grid, filters, grouping, annotations, search, dialogs."""

import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\fireblade-test\harness")
import fbcommon as fb

fb.prepare_environment()

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

app = QApplication(sys.argv)
fb.install_language(app)
journal = fb.Journal("explore")
watch = fb.ModalWatchdog(app, journal)

from fireblade.ui.app import Window  # noqa: E402
from fireblade.core.collection import ToolPack  # noqa: E402
import fireblade.ui.collection as uic  # noqa: E402

TOOLS = r"C:\fireblade-test\tools"
Window.toolpack = lambda self: ToolPack(TOOLS)

SOURCE = r"C:\fireblade-test\collecte-demo"
screen = fb.work_screen(app)
window = Window(require_case=False)
fb.place(window, screen)
window.setAttribute(Qt.WA_ShowWithoutActivating, True)
window.show()
window.raise_()
fb.settle(app, 800)

captured = {}


def modal(opener, name, prepare=None, accept=True, wait_ms=900):
    """Open a modal, photograph it, then close it. Never leave one open."""
    result = {}

    def act():
        dialog = app.activeModalWidget()
        if dialog is None:
            QTimer.singleShot(250, act)
            return
        try:
            if prepare:
                prepare(dialog)
            fb.settle(app, 600)
            result["shot"] = fb.shot(dialog, name)
            result["title"] = dialog.windowTitle()
        except Exception as exc:  # noqa: BLE001
            result["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            (dialog.accept if accept else dialog.reject)()

    QTimer.singleShot(wait_ms, act)
    opener()
    fb.settle(app, 600)
    return result


def select(needle):
    return fb.select_analysis(window, app, needle)


def column_named(needle):
    headers = window.case.headers
    return next(i for i, name in enumerate(headers) if needle.casefold() in str(name).casefold())


# ---------------------------------------------------------------- import or reopen the demo
records, errors = window.investigation_library.list()
existing = next((row["id"] for row in records if row["name"] == "VARLOG-DEMO"), None)
if existing:
    window.open_investigation(existing)
    fb.wait(app, lambda: fb.idle(window) and window.centralWidget().isEnabled(), 900)
    fb.settle(app, 2500)
    journal.add("DEMO", "OK", f"case reopened with {len(window.documents)} analyses")
else:
    uic.choose_import_sources = lambda parent=None: [SOURCE]

    def choose_one_grid_per_file(dialog):
        dialog.progressive.setChecked(True)
        return QDialog.Accepted

    uic.CollectionOrganizationDialog.exec = choose_one_grid_per_file
    window.create_investigation("VARLOG-DEMO", "Recette finale 0.4.0 - jeu interactif", "linux")
    fb.settle(app, 1000)
    started = time.monotonic()
    window.parse_collection()
    fb.settle(app, 1500)
    last_note = 0
    while True:
        app.processEvents()
        elapsed = int(time.monotonic() - started)
        report = window.collection.report if window.collection else {}
        done = sum(
            1
            for entry in report.get("files", [])
            if entry.get("status") not in ("pending", "running")
        )
        if elapsed - last_note >= 30:
            last_note = elapsed
            journal.add(
                "DEMO",
                "RUNNING",
                f"{done}/{len(report.get('files', []))} files, "
                f"{len(report.get('documents', []))} analyses, {elapsed}s: "
                + window.statusBar().currentMessage()[:120],
            )
        if fb.idle(window) and window.centralWidget().isEnabled():
            break
        if elapsed > 1800:
            journal.add("DEMO", "FAIL", "import did not finish in 30 minutes")
            break
        time.sleep(0.5)
    fb.wait(app, lambda: fb.idle(window) and window.centralWidget().isEnabled(), 900)
    journal.add(
        "DEMO",
        "OK",
        f"{len(window.documents)} analyses in {time.monotonic() - started:.0f}s",
        time.monotonic() - started,
    )

journal.add("DEMO", "OK", "demo workspace", None, {"shot": fb.shot(window, "E00-demo-workspace")})

# The tab strip is what the analyst reads: measure its labels, not the evidence basenames.
labels = list(
    getattr(window.tabs, "labels", [])
    or [Path(doc.source_info.get("path", "")).name for doc in window.documents]
)
duplicates = len(labels) - len(set(labels))
journal.add(
    "D22",
    "REVIEW" if duplicates else "OK",
    f"{len(labels)} analyses, {duplicates} share an identical tab label",
    None,
    {"labels": sorted(set(labels))[:6], "shot": fb.shot(window, "D22-tab-labels")},
)

# ---------------------------------------------------------------- E: exploration
select("apache2")
window.workbench.setCurrentIndex(0)
fb.settle(app, 800)
journal.add("E01", "OK", "grid on apache/access.log", None, {"shot": fb.shot(window, "E01-grid")})

begin = time.monotonic()
window.column_search(column_named("Méthode"), "POST")
fb.wait(app, lambda: not window.busy, 120)
fb.settle(app, 600)
journal.add(
    "E01",
    "OK",
    f"column filter POST in {time.monotonic() - begin:.2f}s",
    time.monotonic() - begin,
    {"shot": fb.shot(window, "E01-column-filter")},
)

window.clear_filters()
fb.settle(app, 500)
begin = time.monotonic()
window.set_sort(column_named("Statut"), True)
fb.wait(app, lambda: not window.busy, 120)
fb.settle(app, 500)
journal.add(
    "E02",
    "OK",
    f"sort descending on Statut in {time.monotonic() - begin:.2f}s",
    time.monotonic() - begin,
    {"shot": fb.shot(window, "E02-sort")},
)

window.sort_options.setVisible(True)
window.sort_column.setCurrentIndex(min(2, window.sort_column.count() - 1))
window.sort_type.setCurrentIndex(1)
fb.settle(app, 700)
journal.add("E02", "OK", "sort options bar", None, {"shot": fb.shot(window, "E02-sort-options")})
window.sort_options.setVisible(False)

journal.add(
    "E03",
    "OK",
    "multi-column sort dialog",
    None,
    modal(window.edit_sort, "E03-multi-sort", accept=False),
)

journal.add(
    "E04",
    "OK",
    "AND/OR/NOT editor",
    None,
    modal(window.edit_filters, "E04-filter-editor", accept=False),
)

window.filter_value(column_named("Statut"), "404")
fb.wait(app, lambda: not window.busy, 120)
fb.settle(app, 600)
journal.add(
    "E05",
    "OK",
    "filter on active cell",
    None,
    {"shot": fb.shot(window, "E05-filter-cell"), "filters": window.filters.count()},
)
window.clear_filters()
fb.settle(app, 600)

window.group_column(column_named("Adresse distante"))
window.group_column(column_named("Statut"), append=True)
fb.wait(app, lambda: not window.busy, 120)
fb.settle(app, 1000)
journal.add(
    "E06",
    "OK",
    "two grouping levels",
    None,
    {"shot": fb.shot(window, "E06-grouping"), "groups": list(window.view.groups)},
)

journal.add(
    "E08",
    "OK",
    "group summaries dialog",
    None,
    modal(window.edit_groups, "E08-group-summaries", accept=False),
)

window.expand_groups()
fb.settle(app, 900)
journal.add("E09", "OK", "expand all groups", None, {"shot": fb.shot(window, "E09-expanded")})
window.collapse_groups()
fb.settle(app, 700)
window.group_column(0, clear=True)
fb.wait(app, lambda: not window.busy, 120)
fb.settle(app, 600)

journal.add(
    "E10", "OK", "column manager", None, modal(window.columns, "E10-column-manager", accept=False)
)

window.pin_column(1)
fb.settle(app, 600)
journal.add("E11", "OK", "pin a column", None, {"shot": fb.shot(window, "E11-pinned")})
window.pin_column(1)

journal.add(
    "E12",
    "OK",
    "row heights dialog",
    None,
    modal(window.edit_row_heights, "E12-row-heights", accept=False),
)

index = window.model.index(3, 3)
window.tree.setCurrentIndex(index)
journal.add(
    "E13",
    "OK",
    "cell details (JSON)",
    None,
    modal(window.cell_details, "E13-cell-details", accept=False),
)

fb.select_row(window, 2)
window.copy_rows()
fb.settle(app, 300)
journal.add("E14", "OK", "copy rows", f"{len(app.clipboard().text())} characters on the clipboard")

begin = time.monotonic()
window.search.setText("203.0.113.7")
result = modal(window.find_workspace, "E15-cross-search", wait_ms=2500)
fb.wait(app, lambda: not window.busy, 120)
fb.settle(app, 800)
journal.add(
    "E15",
    "OK",
    f"cross-analysis search in {time.monotonic() - begin:.2f}s",
    time.monotonic() - begin,
    dict(result, shot_after=fb.shot(window, "E15-cross-search-results")),
)
window.search.setText("")

journal.add(
    "E16", "OK", "highlight dialog", None, modal(window.highlight, "E16-highlight", accept=False)
)

window.toggle_bookmark(window.model.index(2, 0))
fb.settle(app, 700)
journal.add("F01", "OK", "bookmark a row", None, {"shot": fb.shot(window, "F01-bookmark")})

row_index = next(
    (
        row
        for row in range(window.model.rowCount())
        if not window.model.node(window.model.index(row, 0)).group
    ),
    None,
)
assert row_index is not None, "no data row to annotate"
row_id = window.model.node(window.model.index(row_index, 0)).values[0]
journal.add(
    "F02",
    "OK",
    "note dialog on a row",
    None,
    modal(lambda: window.edit_bookmark(row_id), "F02-row-note", accept=False),
)

journal.add(
    "F03",
    "OK",
    "note dialog on a cell",
    None,
    modal(lambda: window.edit_bookmark(row_id, 2), "F03-cell-note", accept=False),
)

fb.select_row(window, 4)
journal.add(
    "F04",
    "OK",
    "selection note dialog",
    None,
    modal(lambda: window.annotate_selection("append"), "F04-selection-note", accept=False),
)

window.only_notes.setChecked(True)
fb.wait(app, lambda: not window.busy, 120)
fb.settle(app, 700)
journal.add("E17", "OK", "bookmarks-only filter", None, {"shot": fb.shot(window, "E17-only-notes")})
window.only_notes.setChecked(False)
window.clear_filters()
fb.settle(app, 600)

journal.add(
    "E20", "OK", "messages dialog", None, modal(window.show_messages, "E20-messages", accept=False)
)

journal.add(
    "E19",
    "OK",
    "pagination",
    None,
    {"shot": fb.shot(window, "E19-page-1"), "rows": window.case.count(window.view)},
)
window.more()
fb.wait(app, lambda: not window.busy, 300)
fb.settle(app, 900)
journal.add("E19", "OK", "next page", None, {"shot": fb.shot(window, "E19-page-2")})
window.previous()
fb.settle(app, 500)

journal.add("E18", "OK", "reset view", None, {"shot": fb.shot(window, "E18-reset")})
window.reset()
fb.settle(app, 500)

# ---------------------------------------------------------------- other analyses
select("journal")
fb.settle(app, 800)
journal.add(
    "D09",
    "OK",
    "systemd journal analysis",
    None,
    {"shot": fb.shot(window, "D09-journal"), "rows": window.case.count(window.view)},
)
select("traps")
fb.settle(app, 800)
journal.add("D14", "OK", "traps analysis", None, {"shot": fb.shot(window, "D14-traps")})

window.save_investigation()
fb.settle(app, 800)
journal.add("DONE", "OK", "exploration section finished")
window.close()
