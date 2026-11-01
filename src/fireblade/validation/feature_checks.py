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
        # Exercise serialized summary sorting and custom appearances inside the EXE.
        from fireblade.core.tle_layout import read_tle_layout
        record='colType,Descending,#0'
        state=str(len(record))+':'+record
        xml=directory/'summary-style.layout'
        xml.write_text(f'<XtraSerializer><property name="Columns"><property name="Item1"><property name="FieldName">Type</property><property name="Name">colType</property><property name="GroupIndex">0</property></property></property><property name="GroupSummary"><property name="Item1"><property name="FieldName">ID</property><property name="SummaryType">Sum</property></property></property><property name="GroupSummarySortInfoState">{state}</property><property name="Appearance"><property name="GroupRow"><property name="BackColor">#daf0da</property><property name="Font">Arial, 10pt, style=Bold</property></property><property name="HeaderPanel"><property name="ForeColor">#123456</property></property></property></XtraSerializer>',encoding='utf-8')
        window.apply_tle_layout(read_tle_layout(xml,case.headers));settle()
        index=window.model.index(0,0)
        expect(window.model.node(index).values[0]=='A','Imported summary sorting changed the group order')
        expect(index.data(Qt.BackgroundRole).name()=='#daf0da' and index.data(Qt.FontRole).bold(),'Imported group appearance is missing')
        expect(window.model.headerData(1,Qt.Horizontal,Qt.ForegroundRole).name()=='#123456','Imported header appearance is missing')
        from fireblade.validation.layout_appearance import check_layout_appearance
        check_layout_appearance(window,directory,settle,expect,captures)
    check('group_summaries_sort_and_exact_large_values',summaries)

    def mixed_icons():
        from fireblade.validation.layout_appearance import check_mixed_icon_layout
        check_mixed_icon_layout(window,directory,settle,expect)
    check('mixed_icon_threshold_units_and_pinned_rendering',mixed_icons)

    def priority_appearance():
        from fireblade.validation.layout_appearance import check_priority_layout
        check_priority_layout(window,directory,settle,expect)
    check('high_priority_layout_and_selection_rendering',priority_appearance)

    def alpha_appearance():
        from fireblade.validation.layout_appearance import check_alpha_layout
        check_alpha_layout(window,directory,settle,expect,captures)
    check('argb_layout_pixels_light_dark_and_selection',alpha_appearance)

    def group_footers():
        from fireblade.validation.group_footers import check_group_footers
        check_group_footers(window,directory,settle,expect,captures)
    check('separate_group_global_footers_and_source_export',group_footers)

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
        window.pin_column(2, 'right')
        QApplication.processEvents()
        right=window.tree.right_frozen;index=window.model.index(0,3)
        expect(right.model() is window.model and right.selectionModel() is window.tree.selectionModel(),'Right pin has an independent model or selection')
        expect(right.isVisible() and right.visualRect(index).isValid(),'Right-pinned record is invisible')
        expect(window.visible_columns()[-1]==2,'Right pin not last in copy/export order')
        expect(window.tree.frozen.geometry().right()<window.tree.viewport().geometry().left(),'Left pin overlaps center')
        expect(window.tree.viewport().geometry().right()<right.geometry().left(),'Right pin overlaps center')
        before=right.geometry()
        window.tree.horizontalScrollBar().setValue(window.tree.horizontalScrollBar().maximum());QApplication.processEvents()
        expect(right.geometry()==before,'Right pin moved with horizontal scroll')
        rendered_contrast(right.viewport(),right.visualRect(index).adjusted(5,3,-5,-3))
        expect(View.from_json(window.view.to_json()).right_pinned_columns==[2],'Right pin lost on view serialization')
        if captures:window.grab().save(str(Path(captures)/'extended-pinned-right.png'))
        right.setColumnWidth(3,279)
        window.save_format_layout()
        saved=copy.deepcopy(window.view)
        window.set_view(View());settle()
        expect(window.restore_format_layout(),'No automatic layout found for the current format')
        settle()
        expect(window.view.right_pinned_columns==saved.right_pinned_columns,'Automatic layout lost right pins')
        expect(window.tree.right_frozen.columnWidth(3)==279,'Automatic layout lost pinned width')
        window.pin_column(2)
        window.pin_column(4)
        window.tree.horizontalScrollBar().setValue(0)
    check('pinned_columns_share_selection_and_survive_horizontal_scroll',pins)

    def filter_and_export():
        view=View(expression=parse_filter("[Type] = 'A' And [ID] >= 1",case.headers),sort_column=2,sort_type='number')
        window.set_view(view);settle()
        expect(case.count(view)==2,'Text expression filter incorrect')
        advanced=View(expression=parse_filter("@Type='A' And InRange(ToInt(ID),1m,9007199254740994m) And IsJanuary(Date)",case.headers))
        expect(case.count(advanced)==2,'Advanced criteria syntax changed filtering')
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
        ps=directory/'powershell.csv'
        ps.write_text('#TYPE System.Object\nUser,Command\nalice,Get-Process\n#TYPE kept,Get-Date\n')
        imported=Case(directory/'powershell.timeline',settings=window.settings)
        try:
            imported.import_csv(ps)
            expect(imported.page(View())==[(1,'alice','Get-Process'),(2,'#TYPE kept','Get-Date')],'PowerShell metadata handling lost data')
        finally:imported.close()
    check('bundled_forensic_catalog_and_legacy_excel_dependency',schema_plugins)

    def legacy_session():
        session=directory/'legacy.tle_sess'
        session.write_text(json.dumps({'SessionFiles':{str(source):[2]}}))
        snapshots=TleSessionImport(read_tle_session(session),directory/'converted',window.settings).run()
        converted=Case(snapshots[0].path,settings=window.settings)
        try:expect(converted.bookmarks()=={2:''},'Imported TLE tags are incorrect')
        finally:converted.close()
        from fireblade.core.tle_session_export import TleSessionExport
        exported=directory/'exported-session.tle_sess'
        expect(TleSessionExport(snapshots,window.settings).run(exported)==1,'TLE session export did not include the source')
        expect(read_tle_session(exported)==[(source.resolve(),[2])],'Exported TLE source/tag contract changed')
        reimported=TleSessionImport(read_tle_session(exported),directory/'roundtrip',window.settings).run()
        reopened=Case(reimported[0].path,settings=window.settings,read_only=True)
        try:expect(reopened.bookmarks()=={2:''},'TLE export/import lost source tag identity')
        finally:reopened.close()
    check('timeline_explorer_session_sources_and_tags',legacy_session)

    def preferences():
        original=copy.deepcopy(window.preferences)
        try:
            window.preferences.multiline_tabs=True
            window.preferences.theme='dark'
            window.tabs.setFixedWidth(260)
            window.apply_preferences();QApplication.processEvents()
            from PySide6.QtTest import QTest
            before=window.active_document
            bar,local=window.tabs.tab_widget(0)
            rect=bar.tabRect(local).intersected(bar.rect())
            expect(rect.isValid(),'First wrapped tab has no visible click target')
            bar_geometry=bar.geometry().getRect()
            QTest.mouseClick(bar,Qt.LeftButton,pos=rect.center());settle()
            expect(str(window.case.path)==window.documents[0].path,
                   f'Wrapped tab did not switch: active={window.active_document}, rect={rect.getRect()}, bar={bar_geometry}')
            bar,local=window.tabs.tab_widget(before)
            rect=bar.tabRect(local).intersected(bar.rect())
            expect(rect.isValid(),'Return tab has no visible click target')
            QTest.mouseClick(bar,Qt.LeftButton,pos=rect.center());settle()
            expect(window.active_document==before,'Return click did not restore the original document')
            from fireblade.validation.appearance import rendered_contrast
            bar=window.menuBar()
            rendered_contrast(bar,bar.actionGeometry(bar.actions()[0]).adjusted(4,2,-4,-2))
            if captures:
                window.grab().save(str(Path(captures)/'extended-dark.png'))
        finally:
            window.tabs.setMinimumWidth(0)
            window.tabs.setMaximumWidth(16777215)
            window.preferences=original
            window.apply_preferences()
            QApplication.processEvents()
    check('dark_theme_actual_glyphs_and_wrapped_tabs',preferences)


    def automatic_heights():
        from fireblade.validation.row_heights import check_auto_row_heights
        check_auto_row_heights(window,directory,expect,captures)
    check('automatic_multiline_row_heights_and_pinned_scrolling',automatic_heights)

    def long_headers():
        from fireblade.validation.row_heights import check_progressive_header_probe
        check_progressive_header_probe(directory,expect)
    check('progressive_complete_header_probe_utf8_utf16_utf32',long_headers)

    def xml_export():
        from fireblade.core.models import Filter,FilterGroup
        from fireblade.core.tle_layout_export import write_tle_layout
        from fireblade.core.tle_layout import read_tle_layout
        from fireblade.core.tle_settings import read_tle_settings
        from fireblade.core.preferences import default_pinned_columns
        import hashlib
        source=directory/'xml-export-source.csv'
        source.write_text('User,Value\nalice,1\nbob,2\nalice,3\n',encoding='utf-8')
        original=hashlib.sha256(source.read_bytes()).hexdigest()
        case=Case(directory/'xml-export.timeline',settings=window.settings)
        try:
            case.import_csv(source)
            view=View(groups=[0],summaries=[Summary(1,'sum','number',1)],group_footer_mode='always',
                      expression=FilterGroup('and',[Filter(1,'ge','2')]),auto_row_height=True,
                      layout_styles={'row':{'background':'#80102030','word_wrap':True}})
            columns=[dict(column=0,position=0,width=210),dict(column=1,position=1,width=180)]
            target=directory/'exported-tle.layout'
            write_tle_layout(target,case.headers,view,columns)
            restored=read_tle_layout(target,case.headers)
            case.validate_view(restored.view)
            expect(case.count(view)==case.count(restored.view)==2,'XML export changed selected source events')
            expect(restored.view.summaries==view.summaries and restored.view.group_footer_mode=='always','XML export changed group footers')
            expect(restored.view.layout_styles==view.layout_styles,'XML export lost ARGB or wrapping')
            expect(hashlib.sha256(source.read_bytes()).hexdigest()==original,'XML export changed evidence')
            prefs=directory/'scoped-pins.xml'
            prefs.write_text('<Settings><FirstPinnedColumns><Entry><Key>GenericCsv</Key><Value><string>Value</string></Value></Entry></FirstPinnedColumns></Settings>')
            preferences=read_tle_settings(prefs).preferences
            expect(default_pinned_columns(preferences,case.headers,{})==[1],'Structured reader pin mapping was lost')
        finally:case.close()
    check('tle_xml_layout_export_and_scoped_default_pins',xml_export)

    def gallery():
        from fireblade.validation.theme_gallery import check_theme_gallery
        check_theme_gallery(window,captures)
    check('gallery_themes_and_isolated_preview',gallery)
