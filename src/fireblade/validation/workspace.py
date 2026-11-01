"""320 real databases in the frozen app, with actual QtTest tab clicks."""
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtTest import QTest

from fireblade.core.engine import Case
from fireblade.ui.cross_search import WorkspaceSearch
from fireblade.ui.workspace import read_session
from fireblade.validation.gui_driver import GuiRun


COUNT = 320


def run_workspace(app, report_path):
    run = GuiRun(app, report_path, 'many-document-workspace')
    error = None
    window = run.window
    sources = run.out/'sources'
    sources.mkdir()
    window.resize(1000, 700)
    window.preferences.multiline_tabs = True
    window.apply_preferences()
    try:
        def imports():
            for index in range(COUNT):
                source = sources/f'case-{index:03}.csv'
                source.write_text(f'Marker,User\ncase-{index:03},alice\n', encoding='utf-8')
                target = sources/f'case-{index:03}.timeline'
                def import_one(source=source, target=target):
                    case = Case(target, settings=window.settings)
                    try:
                        case.import_csv(source)
                        return case
                    except BaseException:
                        case.close()
                        raise
                case = run.work(import_one)
                window.detach()
                window.attach(case)
                run.settle()
                QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
                run.report['imported_documents'] = index + 1
            assert len(window.documents) == window.tabs.count() == COUNT
            assert window.tabs.height() <= 3 * max(bar.sizeHint().height() for bar in window.tabs.rows)
            run.capture('320-open-analyses')
            return dict(documents=COUNT, rows_per_file=1, scroll_maximum=window.tabs.area.verticalScrollBar().maximum())
        run.check('import_320_distinct_csv_databases', imports)

        def navigation():
            visited = []
            for index in (0, 159, 319):
                # Scroll without activating, then click the visible tab itself.
                bar, local = window.tabs.tab_widget(index)
                window.tabs.area.ensureWidgetVisible(bar, 0, 0)
                app.processEvents()
                QTest.mouseClick(bar, Qt.LeftButton, pos=bar.tabRect(local).center())
                run.settle()
                assert window.active_document == index
                assert window.model.data(window.model.index(0, 1)) == f'case-{index:03}'
                visited.append(index)
            run.capture('last-analysis-selected')
            return dict(visited=visited)
        run.check('click_first_middle_last_analysis', navigation)

        def search():
            hits = run.work(lambda: WorkspaceSearch(window.documents, window.settings, window.case).find('alice'))
            assert len(hits) == COUNT and all(hit.count == 1 and not hit.error for hit in hits)
            return dict(analyses=len(hits), matching_rows=sum(hit.count for hit in hits), errors=0)
        run.check('search_all_320_analyses', search)

        def session():
            target = run.out/'all.fireblade-session'
            window.save_session(target)
            snapshots, active = read_session(target)
            assert len(snapshots) == COUNT and active == 319
            window.load_session(target)
            run.settle()
            assert len(window.documents) == COUNT and window.active_document == 319
            assert window.model.data(window.model.index(0, 1)) == 'case-319'
            run.capture('restored-320-analysis-session')
            return dict(saved=COUNT, restored=len(window.documents), active=window.active_document)
        run.check('save_and_restore_320_analysis_session', session)
    except Exception as exc:
        error = exc
    return run.finish(error)
