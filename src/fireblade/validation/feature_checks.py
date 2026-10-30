"""Acceptance checks for the expanded desktop, run inside the bundled EXE."""
import copy
import csv
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from fireblade.core.engine import Case
from fireblade.core.filter_text import parse_filter
from fireblade.core.models import Summary, View
from fireblade.core.profiles import detect_profile, profile_view
from fireblade.core.tle_compat import read_tle_session, TleSessionImport
from fireblade.ui.cross_search import WorkspaceSearch


def check_features(window, directory, settle, check, expect, captures=None):
    directory = Path(directory)
    # Use a new analysis: the preceding checks can leave rules or annotations.
    source=directory/'fonctions étendues.csv'
    source.write_text('Date,Type,ID,Flag,User\n2026-01-01 01:00:00.1234567,A,9007199254740993,TRUE,alice\n2026-01-02 02:00:00,A,1,FALSE,bob\n2026-02-01 03:00:00,B,5,TRUE,alice\n')
    case=Case(directory/'fonctions.timeline',settings=window.settings)
    case.import_csv(source)
    window.detach()
    window.attach(case)
    settle()

    def summaries():
        view=View(groups=[1],summaries=[Summary(2,'sum'),Summary(2,'max')],group_order='summary')
        window.set_view(view);settle()
        values=window.model.node(window.model.index(0,0)).values
        expect(values[0]=='A' and str(values[2]).startswith('9007199254740994'),'Group summary lost integer precision')
        target=directory/'résumés.csv';case.export(target,view,grouped=True)
        expect('sum(ID)' in target.read_text(encoding='utf-8-sig'),'Missing summary export')
    check('group_summaries_sort_and_exact_large_values',summaries)

    def periods():
        view=View(groups=[0],group_intervals={'0':'month'},group_order='value',group_descending=False)
        window.set_view(view);settle()
        first=window.model.index(0,0)
        expect(window.model.node(first).values==('2026-01',2),'Temporal group count incorrect')
        window.tree.setExpanded(first,True);settle()
        expect(window.model.rowCount(first)==2,'Temporal group navigation failed')
        window.collapse_groups();settle()
        expect(window.model.rowCount(first)==0,'Collapsing did not release rows')
    check('date_period_groups_expand_and_release',periods)

    def pins():
        window.set_view(View());settle()
        window.pin_column(4)
        QApplication.processEvents()
        expect(window.tree.frozen.model() is window.model,'Pinned grid duplicated its data model')
        expect(window.tree.frozen.columnWidth(5)>0 and window.tree.frozen.isVisible(),'Pinned field not visible')
        expect(4 in window.visible_columns(),'Pinned field missing from export projection')
        from fireblade.validation.appearance import rendered_contrast
        rect=window.tree.frozen.visualRect(window.model.index(0,5))
        expect(rect.isValid() and rect.height()>0,'Pinned row is not laid out')
        rendered_contrast(window.tree.frozen.viewport(),rect.adjusted(5,3,-5,-3))
        window.tree.horizontalScrollBar().setValue(window.tree.horizontalScrollBar().maximum())
        expect(window.tree.frozen.isVisible(),'Pinned columns disappeared on scroll')
        if captures:
            window.grab().save(str(Path(captures)/'extended-pinned.png'))
        window.pin_column(4)
        window.tree.horizontalScrollBar().setValue(0)
    check('pinned_columns_share_selection_and_survive_horizontal_scroll',pins)

    def filter_and_export():
        view=View(expression=parse_filter("[Type] = 'A' And [ID] >= 1",case.headers),sort_column=2,sort_type='number')
        window.set_view(view);settle()
        expect(case.count(view)==2,'Text expression filter incorrect')
        target=directory/'projection.csv'
        case.export(target,view,columns=[4,2])
        with target.open(encoding='utf-8-sig',newline='') as incoming:
            expect(list(csv.reader(incoming))==[['User','ID'],['bob','1'],['alice','9007199254740993']],'Export ignored projection or exact values')
    check('text_filter_syntax_and_visible_order_export',filter_and_export)

    def cross_search():
        window.remember_active()
        task=WorkspaceSearch(window.documents,window.settings,case)
        hits=task.find('alice')
        current=next(h for h in hits if h.path==str(case.path))
        expect(current.count==2 and not current.error,'Cross-file search failed on current analysis')
        expect(len(hits)==len(window.documents),'Search omitted an analysis')
        expect(all(h.count is not None for h in hits),'Search encountered an unexplained error')
    check('search_all_open_analyses_with_sequential_connections',cross_search)

    def booleans():
        window.set_view(View(boolean_columns=[3],timestamp_columns=[0]));settle()
        window.model.date_format='iso7'
        expect(window.model.data(window.model.index(0,4),Qt.CheckStateRole)==Qt.Checked,'Boolean true not a checkbox')
        expect(window.model.data(window.model.index(1,4),Qt.CheckStateRole)==Qt.Unchecked,'Boolean false not a checkbox')
        expect('.1234567' in window.model.data(window.model.index(0,1)),'Timestamp precision was lost')
        window.model.setData(window.model.index(0,0),Qt.Checked,Qt.CheckStateRole);settle()
        expect(case.bookmarks().get(1) is not None,'Clickable bookmark checkbox failed')
    check('boolean_cells_bookmark_checkbox_and_timestamp_precision',booleans)

    def closed():
        path=case.path
        window.close_document(window.active_document);settle()
        window.reopen_closed();settle()
        expect(window.case.path==path and window.case.bookmarks().get(1) is not None,'Reopened tab lost data or notes')
    check('reopen_closed_analysis_retains_view_and_notes',closed)

    def schema_plugins():
        headers=['Timestamp','RuleTitle','Level','Computer','Channel','EventID','RecordID','Details','ExtraFieldInfo']
        profile=detect_profile(headers)
        expect(profile is not None and profile.name=='HayabusaStandard','Bundled forensic catalog unavailable')
        view,_=profile_view(profile,headers)
        expect(view.timestamp_columns==[0] and bool(view.format_rules),'Catalog typing or severity rules absent')
        import xlrd
        expect(xlrd.__version__=='2.0.2','Legacy XLS reader not bundled')
    check('bundled_forensic_catalog_and_legacy_excel_dependency',schema_plugins)

    def legacy_session():
        session=directory/'legacy.tle_sess'
        session.write_text(json.dumps({'SessionFiles':{str(source):[2]}}))
        snapshots=TleSessionImport(read_tle_session(session),directory/'converted',window.settings).run()
        converted=Case(snapshots[0].path,settings=window.settings)
        try:expect(converted.bookmarks()=={2:''},'Imported TLE tags are incorrect')
        finally:converted.close()
    check('timeline_explorer_session_sources_and_tags',legacy_session)

    def preferences():
        original=copy.deepcopy(window.preferences)
        try:
            window.preferences.multiline_tabs=True
            window.preferences.theme='dark'
            window.apply_preferences();QApplication.processEvents()
            from fireblade.validation.appearance import rendered_contrast
            bar=window.menuBar()
            rendered_contrast(bar,bar.actionGeometry(bar.actions()[0]).adjusted(4,2,-4,-2))
            if captures:
                window.grab().save(str(Path(captures)/'extended-dark.png'))
        finally:
            window.preferences=original
            window.apply_preferences()
            QApplication.processEvents()
    check('dark_theme_actual_glyphs_and_wrapped_tabs',preferences)
